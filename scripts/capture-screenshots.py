#!/usr/bin/env python3
"""Take real 1920x1080 screenshots of a brussels image that boots in QEMU.

The input is a disk image made with `bootc install to-disk` and the kernel
arguments of `just generate-bootable-image`. Only systemd.debug_shell=ttyS1
is necessary: it gives the script a root shell on the second serial port.
QEMU runs with -snapshot, so the disk image does not change.

The script makes a demo user in the running VM, logs in through the greeter
with QMP key events, starts the applications of the image, and saves the
framebuffer with the QMP `screendump` command. It does not edit a picture.
docs/winblues.md tells how to use it.
"""

from __future__ import annotations

import argparse
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
        self.sock.sendall(f"{command}; echo \"END\"\"{self.count}END:$?\"\n".encode())
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
            if match := re.search(rf"{marker}:(\d+)", text):
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

    def in_session(self, command: str) -> None:
        """Start a program of the image as a client of the demo session."""
        env = (
            "XDG_RUNTIME_DIR=/run/user/$(id -u demo) "
            "DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/$(id -u demo)/bus "
            "WAYLAND_DISPLAY=$(cd /run/user/$(id -u demo) && ls -d wayland-? | head -n1) "
            "XDG_SESSION_TYPE=wayland XDG_CURRENT_DESKTOP=XFCE GDK_BACKEND=wayland"
        )
        self.run(f"(cd /home/demo && runuser -u demo -- env {env} setsid {command} >/dev/null 2>&1 </dev/null &)")


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

    def close(program: str) -> None:
        shell.run(f"pkill -u demo -f '{program}' || true")
        time.sleep(1)

    shell.wait_ready(args.boot_timeout)
    # Keep the kernel log and the greeter away from a first-boot wizard, and
    # keep names of the host out of the pictures.
    shell.run("hostname brussels")
    shell.run(f"id {USER} >/dev/null 2>&1 || useradd -m -c 'Demo User' -s /bin/bash {USER}")
    shell.run(f"echo {USER}:{PASSWORD} | chpasswd")
    shell.wait_for("systemctl is-active -q graphical.target", args.boot_timeout)
    shell.run("systemctl restart display-manager", timeout=120)
    time.sleep(15)

    versions = shell.run(
        "cat /usr/lib/os-release; uname -r;"
        " for p in xfwl4 xfce4-panel xfce4-session thunar xfce4-terminal xfdesktop; do"
        " echo \"== $p\"; timeout 10 runuser -u demo -- $p --version 2>&1 | head -n1; done"
    )
    (args.out / "versions.txt").write_text(versions.replace("\r", ""))

    shot("login")
    if not args.no_login:
        qmp.keys("ret")
        time.sleep(3)
        qmp.type(PASSWORD + "\n")
        shell.wait_for(f"pgrep -u {USER} -x xfce4-panel >/dev/null", 120)
        time.sleep(20)

    shot("desktop")
    qmp.click(30, HEIGHT - 15)
    shot("start-menu")
    qmp.keys("esc")

    for name, program, command in (
        ("file-manager", "thunar", "thunar /usr/share"),
        ("terminal", "xfce4-terminal", "xfce4-terminal -e 'bash -c \"fastfetch; exec bash\"'"),
        ("appearance", "xfce4-appearance-settings", "xfce4-appearance-settings"),
        ("settings", "xfce4-settings-manager", "xfce4-settings-manager"),
        ("about", "xfce4-about", "xfce4-about"),
    ):
        shell.in_session(command)
        time.sleep(4)
        shot(name)
        close(program)

    shell.in_session("thunar /home/demo")
    time.sleep(3)
    shell.in_session("xfce4-terminal -e 'bash -c \"fastfetch; exec bash\"'")
    time.sleep(3)
    shell.in_session("xfce4-appearance-settings")
    time.sleep(3)
    qmp.click(30, HEIGHT - 15)
    shot("hero")
    qmp.keys("esc")


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
    parser.add_argument("--no-login", action="store_true", help="the image logs in without a greeter")
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
