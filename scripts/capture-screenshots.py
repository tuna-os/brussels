#!/usr/bin/env python3
"""Take real 1920x1080 screenshots of a brussels image that boots in QEMU.

The input is a disk image made with `bootc install to-disk` and the kernel
arguments of `just generate-bootable-image`. Only systemd.debug_shell=ttyS1
is necessary: it gives the script a root shell on the second serial port.
QEMU runs with -snapshot, so the disk image does not change.

The script uses the session that the image starts. If the image stops at the
greeter, the script makes a demo user in the running VM and logs in with QMP
key events. Then it starts the applications of the image, and saves the
framebuffer with the QMP `screendump` command. The login picture comes last,
with the automatic login off. The script does not edit a picture.
docs/winblues.md tells how to use it.
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

WIDTH, HEIGHT = 1920, 1080
USER = "demo"
PASSWORD = "demo"  # noqa: S105 - exists only in the throwaway VM

KEYS = {
    "\n": "ret",
    " ": "spc",
    "-": "minus",
    ".": "dot",
    "/": "slash",
    ";": "semicolon",
    "=": "equal",
}


def key_for(char: str) -> list[str]:
    """Return the QMP qcodes that type one character (US layout)."""
    if char in KEYS:
        return [KEYS[char]]
    if char == "_":
        return ["shift", "minus"]
    if char.isascii() and char.isalpha():
        return ["shift", char.lower()] if char.isupper() else [char]
    if char.isascii() and char.isdigit():
        return [char]
    raise ValueError(f"no key mapping for {char!r}")


def connect(path: Path, timeout: float = 30) -> socket.socket:
    deadline = time.monotonic() + timeout
    while True:
        sock = socket.socket(socket.AF_UNIX)
        try:
            sock.connect(str(path))
            return sock
        except OSError:
            sock.close()
            if time.monotonic() > deadline:
                raise
            time.sleep(0.5)


class Qmp:
    def __init__(self, path: Path) -> None:
        self.file = connect(path).makefile("rwb", buffering=0)
        self.file.readline()
        self.run("qmp_capabilities")

    def run(self, command: str, **arguments: object) -> object:
        message: dict[str, object] = {"execute": command}
        if arguments:
            message["arguments"] = arguments
        self.file.write(json.dumps(message).encode() + b"\n")
        while True:
            line = self.file.readline()
            if not line:
                raise RuntimeError("QEMU closed the QMP socket")
            reply = json.loads(line)
            if "error" in reply:
                raise RuntimeError(f"{command}: {reply['error']}")
            if "return" in reply:
                return reply["return"]

    def keys(self, *qcodes: str) -> None:
        self.run("send-key", keys=[{"type": "qcode", "data": q} for q in qcodes])
        time.sleep(0.15)

    def type(self, text: str) -> None:
        for char in text:
            self.keys(*key_for(char))

    def move(self, x: int, y: int) -> None:
        # usb-tablet axes go from 0 to 32767.
        self.run(
            "input-send-event",
            events=[
                {"type": "abs", "data": {"axis": "x", "value": x * 32767 // (WIDTH - 1)}},
                {"type": "abs", "data": {"axis": "y", "value": y * 32767 // (HEIGHT - 1)}},
            ],
        )
        time.sleep(0.3)

    def click(self, x: int, y: int, button: str = "left") -> None:
        self.move(x, y)
        for down in (True, False):
            self.run("input-send-event", events=[{"type": "btn", "data": {"down": down, "button": button}}])
            time.sleep(0.1)

    def drag(self, start: tuple[int, int], end: tuple[int, int]) -> None:
        self.move(*start)
        self.run("input-send-event", events=[{"type": "btn", "data": {"down": True, "button": "left"}}])
        time.sleep(0.2)
        for step in range(1, 11):
            x, y = (a + (b - a) * step // 10 for a, b in zip(start, end, strict=True))
            self.move(x, y)
        self.run("input-send-event", events=[{"type": "btn", "data": {"down": False, "button": "left"}}])


class RootShell:
    """The systemd debug shell on ttyS1."""

    def __init__(self, path: Path, log: Path) -> None:
        self.sock = connect(path)
        self.sock.settimeout(2)
        self.log = log.open("wb")
        self.count = 0

    def run(self, command: str, timeout: float = 60) -> str:
        self.count += 1
        marker = f"END{self.count}END"
        # The quotes keep the marker out of the echo of the command line.
        self.sock.sendall(f'{command}; echo "END""{self.count}END:$?"\n'.encode())
        data = b""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                chunk = self.sock.recv(65536)
            except TimeoutError:
                continue
            if not chunk:
                raise RuntimeError("the serial socket closed")
            self.log.write(chunk)
            self.log.flush()
            data += chunk
            text = re.sub(r"\x1b(\[[0-9;?]*[A-Za-z]|\][^\x07]*\x07|[>=])", "", data.decode(errors="replace"))
            if match := re.search(rf"{marker}:(\d+)\r?\n", text):
                if match[1] != "0":
                    raise RuntimeError(f"exit {match[1]} from: {command}\n{text}")
                return text
        raise TimeoutError(f"no answer from the debug shell to: {command}")

    def wait_ready(self, timeout: float) -> None:
        deadline = time.monotonic() + timeout
        while True:
            try:
                self.run("stty -echo 2>/dev/null; true", timeout=10)
                return
            except (TimeoutError, RuntimeError):
                if time.monotonic() > deadline:
                    raise

    def wait_for(self, test: str, timeout: float) -> None:
        self.run(f"timeout {int(timeout)} sh -c 'until {test}; do sleep 1; done'", timeout=timeout + 10)

    def session_user(self) -> str:
        """Return the owner of the running panel, or an empty string."""
        text = self.run('echo "OW""NER=$(ps -C xfce4-panel -o user:32= | head -n1 | tr -d \' \')"')
        match = re.search(r"OWNER=([\w-]+)", text)
        return match[1] if match else ""

    def in_session(self, user: str, command: str) -> None:
        """Start a program of the image as a client of the XFCE session.

        It gets the environment of the panel, as if the menu started it.
        """
        launcher = f"#!/bin/sh\ncd\nexec setsid setpriv --reuid {user} --regid {user} --init-groups {command}\n"
        encoded = base64.b64encode(launcher.encode()).decode()
        self.run(f"echo {encoded} | base64 -d > /run/shot.sh")
        self.run(
            "xargs -0 -a /proc/$(pgrep -ox xfce4-panel)/environ sh -c "
            "'env -i \"$@\" sh /run/shot.sh >/dev/null 2>&1 </dev/null &' sh"
        )


def qemu_command(args: argparse.Namespace, work: Path) -> list[str]:
    command = [
        args.qemu,
        "-name", "brussels-screenshots", "-machine", "q35,accel=kvm", "-cpu", "host",
        "-m", args.memory, "-smp", str(args.cpus),
        "-drive", f"if=pflash,format=raw,readonly=on,file={args.ovmf_code}",
        "-drive", f"if=pflash,format=raw,file={work / 'vars.fd'}",
        "-drive", f"if=virtio,format={args.format},file={args.disk},snapshot=on",
        "-vga", "none", "-device", f"virtio-vga,xres={WIDTH},yres={HEIGHT}",
        "-device", "qemu-xhci", "-device", "usb-tablet", "-device", "usb-kbd",
        "-nic", "user,model=virtio-net-pci", "-display", "none",
        "-serial", f"file:{args.out / 'serial.log'}",
        "-serial", f"unix:{work / 'shell.sock'},server=on,wait=off",
        "-qmp", f"unix:{work / 'qmp.sock'},server=on,wait=off",
    ]  # fmt: skip
    return command


def capture(args: argparse.Namespace, qmp: Qmp, shell: RootShell) -> None:
    def shot(name: str) -> None:
        time.sleep(args.settle)
        png = args.out / f"{name}.png"
        qmp.run("screendump", filename=str(png.resolve()), format="png")
        print(f"captured {png}", flush=True)

    shell.wait_ready(args.boot_timeout)
    # A generic host name, so that a picture shows no personal data.
    shell.run("hostname brussels")
    shell.wait_for("systemctl is-active -q graphical.target", args.boot_timeout)
    # The clock on the panel must not show a time before the first NTP sync.
    shell.wait_for("test $(date +%Y) -ge 2026", 60)
    time.sleep(30)

    user = shell.session_user()
    if not user:
        user = USER
        shell.run(f"id {USER} >/dev/null 2>&1 || useradd -m -c 'Demo User' -s /bin/bash {USER}")
        shell.run(f"echo {USER}:{PASSWORD} | chpasswd")
        # The image also carries the GNOME session; select the XFCE one.
        shell.run(
            'mkdir -p /var/lib/AccountsService/users && printf "[User]\\nSession=%s\\n"'
            " $(basename -s .desktop $(ls -d /usr/share/wayland-sessions/xf*.desktop | head -n1))"
            f" > /var/lib/AccountsService/users/{USER}"
        )
        shell.run("systemctl restart display-manager", timeout=120)
        time.sleep(15)
        qmp.keys("ret")
        time.sleep(3)
        qmp.type(PASSWORD + "\n")
        shell.wait_for(f"pgrep -u {USER} -x xfce4-panel >/dev/null", 120)
        time.sleep(20)
    print(f"session of {user}", flush=True)

    versions = shell.run(
        "cat /usr/lib/os-release; uname -r;"
        " for p in xfwl4 xfce4-panel xfce4-session thunar xfce4-terminal xfdesktop; do"
        f' echo "== $p"; timeout 10 setpriv --reuid {user} --clear-groups $p --version 2>&1 | head -n1; done'
    )
    (args.out / "versions.txt").write_text(versions.replace("\r", ""))

    def close(program: str) -> None:
        shell.run(f"pkill -i -u {user} -f '[{program[0]}]{program[1:]}' || true")
        time.sleep(1)

    def start_menu() -> None:
        qmp.click(30, HEIGHT - 15)

    shot("desktop")
    start_menu()
    shot("start-menu")
    qmp.keys("esc")

    terminal = "xfce4-terminal -e 'bash -c \"head -n7 /usr/lib/os-release; uname -sr; exec bash\"'"
    for name, program, command in (
        ("file-manager", "thunar", "thunar /usr/share"),
        ("terminal", "xfce4-terminal", terminal),
        ("appearance", "xfce4-appearance-settings", "xfce4-appearance-settings"),
        ("settings", "xfce4-settings-manager", "xfce4-settings-manager"),
        ("about", "xfce4-about", "xfce4-about"),
    ):
        # A picture without its program is a wrong picture.
        missing = shell.run(f"ldd $(command -v {program}) 2>&1 | grep -c 'not found' || true")
        if not re.search(r"^0\r?$", missing, re.MULTILINE):
            print(f"NOT captured: {name}: {program} cannot start in this image", flush=True)
            continue
        shell.in_session(user, command)
        shell.wait_for(f"pgrep -i -u {user} -f '[{program[0]}]{program[1:]}' >/dev/null", 30)
        time.sleep(4)
        shot(name)
        close(program)

    # Two windows next to each other: xfwl4 puts a new window in the center.
    for command, title, target in (
        ("thunar /usr/share", (960, 296), (620, 240)),
        ("xfce4-appearance-settings", (960, 253), (1290, 200)),
    ):
        shell.in_session(user, command)
        time.sleep(5)
        qmp.drag(title, target)
        time.sleep(1)
    start_menu()
    shot("hero")
    qmp.keys("esc")

    # Last, because it ends the session.
    shell.run("sed -i 's/^AutomaticLoginEnable=.*/AutomaticLoginEnable=False/' /etc/gdm/custom.conf || true")
    shell.run("systemctl restart display-manager", timeout=120)
    time.sleep(20)
    shot("login")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("disk", type=Path, help="disk image from `bootc install to-disk`")
    parser.add_argument("out", type=Path, help="directory for the PNG files and logs")
    parser.add_argument("--format", default="raw", help="disk image format (default: raw)")
    parser.add_argument("--ovmf-code", required=True, type=Path)
    parser.add_argument("--ovmf-vars", required=True, type=Path)
    parser.add_argument("--qemu", default=shutil.which("qemu-system-x86_64") or "qemu-system-x86_64")
    parser.add_argument("--memory", default="8G")
    parser.add_argument("--cpus", type=int, default=6)
    parser.add_argument("--boot-timeout", type=float, default=240)
    parser.add_argument("--settle", type=float, default=3, help="seconds to wait before each picture")
    args = parser.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="brussels-shots-") as tmp:
        work = Path(tmp)
        shutil.copyfile(args.ovmf_vars, work / "vars.fd")
        vm = subprocess.Popen(qemu_command(args, work))
        try:
            qmp = Qmp(work / "qmp.sock")
            shell = RootShell(work / "shell.sock", args.out / "shell.log")
            try:
                capture(args, qmp, shell)
            except Exception:
                # Keep the state that stopped the run.
                qmp.run("screendump", filename=str((args.out / "failure.png").resolve()), format="png")
                raise
            qmp.run("quit")
        finally:
            vm.terminate()
            vm.wait(timeout=30)
    return 0


if __name__ == "__main__":
    sys.exit(main())
