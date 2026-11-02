#!/usr/bin/env python3
"""Observe the existing Brussels VM and consume the pinned TunaOS visual engine.

Observer-assisted evidence, not uninstrumented or physical-device qualification.
No guest preference, package, account, policy or session mutation is permitted.
"""
import argparse
from contextlib import contextmanager
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
ENGINE_REVISION = "0b577a9eb2d83b49eecbaf25d083f458e003e70b"
ASSETS = {
    "/usr/share/backgrounds/TunaOS/Brussels/brussels-wallpaper.png": "branding/brussels/brussels-wallpaper.png",
    "/usr/share/icons/hicolor/scalable/apps/brussels-logo.svg": "branding/brussels/brussels-logo.svg",
    "/usr/share/tunaos/branding/xfce-linux-wordmark.svg": "branding/brussels/xfce-linux-wordmark.svg",
}
LIVE = "/tmp/xfce-linux-qemu-live.sock"
INSTALLED = "/tmp/xfce-linux-qemu-installed.sock"
SERIAL = "/tmp/xfce-linux-qemu-installed-serial.log"


def sha(path):
    with open(path, "rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def run(*args, **kwargs):
    return subprocess.run(args, check=True, cwd=ROOT, **kwargs)


def hmp(monitor, command):
    with socket.socket(socket.AF_UNIX) as connection:
        connection.settimeout(10)
        connection.connect(monitor)
        connection.recv(4096)
        connection.sendall((command + "\n").encode())
        return connection.recv(16384).decode(errors="replace")


def type_command(monitor, command):
    special = {" ": "spc", "-": "minus", "_": "shift-minus", ".": "dot",
               "/": "slash", ":": "shift-semicolon", ";": "semicolon",
               "'": "apostrophe", '"': "shift-apostrophe", "(": "shift-9", ")": "shift-0"}
    keys = []
    for character in command:
        if character in "abcdefghijklmnopqrstuvwxyz0123456789":
            keys.append(character)
        elif character in special:
            keys.append(special[character])
        else:
            raise ValueError("Unsupported non-secret command key")
    hmp(monitor, "sendkey alt-f2")
    time.sleep(2)
    for key in keys:
        hmp(monitor, "sendkey " + key)
        time.sleep(.06)
    hmp(monitor, "sendkey ret")


def qemu_identity(monitor):
    matches = []
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            args = (entry / "cmdline").read_bytes().split(b"\0")
            if args and any(monitor.encode() in arg for arg in args) and b"qemu-system" in args[0]:
                stat = (entry / "stat").read_text().split(") ", 1)[1].split()
                matches.append({"pid": int(entry.name), "start_ticks": stat[19],
                                "monitor": monitor, "argv": [arg.decode() for arg in args if arg]})
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            continue
    if len(matches) != 1:
        raise RuntimeError("The monitor must identify exactly one owned QEMU process")
    return matches[0]


@contextmanager
def observer(monitor, stage):
    """One private endpoint per observation; never send expected values to guest."""
    token = secrets.token_hex(24)
    receipt_ready = threading.Event()
    done = threading.Event()
    cleaned = threading.Event()
    record = {}
    source = (ROOT / "scripts/brussels-session-observer.py").read_text()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_GET(self):
            if not self.path.startswith("/" + token):
                self.send_error(404)
                return
            if self.path == "/" + token:
                body = (source + f"\nmain({endpoint!r}, {stage!r})\n").encode()
            elif self.path == "/" + token + "/done":
                done.wait(35)
                body = b"{}"
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            if self.path not in ("/" + token + "/receipt", "/" + token + "/cleanup"):
                self.send_error(404)
                return
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 262144:
                self.send_error(413)
                return
            received = json.loads(self.rfile.read(length))
            if self.path.endswith("/cleanup"):
                record["cleanup"] = received
                cleaned.set()
            else:
                record.update(received)
                record["host_received_at"] = time.time()
                record["nonce_sha256"] = hashlib.sha256(token.encode()).hexdigest()
                receipt_ready.set()
            self.send_response(200)
            self.end_headers()

    class Server(ThreadingHTTPServer):
        daemon_threads = True

    server = Server(("127.0.0.1", 0), Handler)
    endpoint = f"http://10.0.2.2:{server.server_port}/{token}"
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        command = f"python3 -c 'import urllib.request;exec(urllib.request.urlopen(\"{endpoint}\").read())'"
        type_command(monitor, command)
        if not receipt_ready.wait(90):
            raise RuntimeError("No active-session observation; capture remains disabled")
        if record.get("error"):
            raise RuntimeError(record["error"])
        session = record.get("session", {})
        if (session.get("Active") != "yes" or session.get("Class") != "user"
                or session.get("Type") not in ("wayland", "x11")
                or str(record.get("uid")) != session.get("User")):
            raise RuntimeError("Observer did not prove an active graphical user session")
        record["qemu"] = qemu_identity(monitor)
        if not record.get("boot_id") or time.time() - record["host_received_at"] > 10:
            raise RuntimeError("Missing or stale active-session observation")
        yield record
    finally:
        done.set()
        cleanup_failed = False
        if stage == "about" and record.get("about_pid"):
            cleanup_failed = not cleaned.wait(12) or not record.get("cleanup", {}).get("about_stopped")
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        if thread.is_alive():
            raise RuntimeError("The owned loopback observer server survived cleanup")
        if cleanup_failed:
            raise RuntimeError("The owned About process did not report bounded cleanup")


def capture(monitor, destination):
    identity = qemu_identity(monitor)
    ppm = destination.with_suffix(".ppm")
    reply = hmp(monitor, "screendump " + str(ppm))
    if "Error" in reply or not ppm.is_file():
        raise RuntimeError("QEMU did not produce the requested actual frame")
    run("convert", str(ppm), str(destination))
    ppm.unlink()
    if qemu_identity(monitor) != identity:
        raise RuntimeError("Owned QEMU changed during capture")
    return {"path": destination.name, "sha256": sha(destination),
            "captured_at": time.time(), "qemu": identity}


def assert_defaults(record, expected):
    if 'PRETTY_NAME="Brussels (TunaOS)"' not in record["os_release"]:
        raise RuntimeError("Observed installed product identity is not Brussels")
    if record["assets"] != expected:
        raise RuntimeError("Observed installed artwork bytes differ from committed source")
    wallpaper = "/usr/share/backgrounds/TunaOS/Brussels/brussels-wallpaper.png"
    values = [line.split(None, 1)[1] for line in record["xfconf"].splitlines()
              if ("last-image" in line or "image-path" in line) and len(line.split(None, 1)) == 2]
    if not values or any(value != wallpaper for value in values):
        raise RuntimeError("The active fresh session did not consume the Brussels wallpaper default")


def assert_encrypted_root(record):
    def mappings(devices):
        for device in devices:
            if device.get("type") == "crypt":
                yield device["name"]
            yield from mappings(device.get("children", []))
    names = set(mappings(record["block_devices"]["blockdevices"]))
    mounts = record["root_mounts"]
    root = mounts.get("/sysroot") or mounts["/"]
    source = root["filesystems"][0]["source"].split("[", 1)[0]
    if not any(source in ("/dev/" + name, "/dev/mapper/" + name) for name in names):
        raise RuntimeError("The actual installed root is not on an observed encrypted mapping")


def assert_installed_identity(record, payload_image):
    observed = record["bootc"]["status"]["booted"]["image"]
    expected_digest = payload_image.rsplit("@", 1)[1]
    if observed.get("imageDigest") != expected_digest:
        raise RuntimeError("Observed bootc digest differs from the exact media payload")


def engine_checkout(directory, source_commit):
    (directory / "scripts").mkdir(parents=True)
    hashes = {}
    for name in ("install-checkpoints.py", "installer-walkthrough.py"):
        url = f"https://raw.githubusercontent.com/tuna-os/tunaOS/{ENGINE_REVISION}/scripts/{name}"
        with urllib.request.urlopen(url, timeout=45) as response:
            (directory / "scripts" / name).write_bytes(response.read())
        hashes[name] = sha(directory / "scripts" / name)
    expected = {}
    for installed, relative in ASSETS.items():
        path = directory / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        contents = subprocess.check_output(["git", "show", f"{source_commit}:{relative}"], cwd=ROOT)
        path.write_bytes(contents)
        expected[installed] = hashlib.sha256(contents).hexdigest()
    return expected, hashes


def admit_checkpoints(summary):
    required = {"live-desktop", "installer-welcome", "luks-before-secret",
                "installed-desktop", "installed-about"}
    rows = summary.get("checkpoints", [])
    return (summary.get("ocr") is True and summary.get("pixels_enforced") is True
            and summary.get("outcome") == "passed"
            and {row["id"] for row in rows if row.get("required")} == required
            and all(row.get("outcome") == "passed" for row in rows if row.get("required")))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target")
    parser.add_argument("channel")
    parser.add_argument("--output", default="output/brussels-visual")
    parser.add_argument("--iso-directory", default="output")
    args = parser.parse_args()
    out = (ROOT / args.output).resolve()
    out.mkdir(parents=True, mode=0o700)
    if any(out.iterdir()):
        raise RuntimeError("Visual evidence directory must be fresh and empty")
    image_directory = (ROOT / args.iso_directory).resolve()
    qualification = json.loads((image_directory / "qualification.json").read_text())
    receipt = {"proof_class": "observer-assisted", "branding_qualified": False,
               "source_commit": qualification["source_commit"],
               "payload_image": qualification["payload_image"],
               "run_id": os.environ.get("GITHUB_RUN_ID", "local"),
               "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT", "1"),
               "iso_sha256": sha(image_directory / f"{args.target}-live.iso"),
               "frames": {}, "observations": {}, "engine_revision": ENGINE_REVISION,
               "capture_state": "pre-secret", "cleanup": {}}
    monitors = {}
    try:
        source_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
        if (qualification["payload_revision"] != qualification["source_commit"]
                or qualification["source_commit"] != source_commit):
            raise RuntimeError("Visual qualification requires the exact checked-out candidate source")
        modules = {}
        for name, path in (
            ("unlock", ROOT / args.target / "src/luks-unlock.py"),
            ("gui", ROOT / "scripts/brussels-gui-install.py"),
        ):
            spec = importlib.util.spec_from_file_location("brussels_" + name, path)
            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)
            modules[name] = module
        receipt["adapter_hashes"] = {str(path.relative_to(ROOT)): sha(path) for path in (
            Path(__file__), ROOT / "scripts/brussels-session-observer.py",
            ROOT / "scripts/brussels-gui-install.py", ROOT / args.target / "src/luks-unlock.py",
            ROOT / "tests/brussels-pipeline-screens.yaml", ROOT / "tests/brussels-installer-screens.yaml",
        )}
        # A fresh per-run test secret is never written to the evidence or argv.
        passphrase = os.environ.get("BRUSSELS_LUKS_PASSPHRASE") or secrets.token_hex(16)
        disk = out / "installed.qcow2"
        scratch = out / "scratch.img"
        boot_options = [f"output_dir={image_directory}", f"luks-qemu-disk={disk}",
                        f"luks-scratch-disk={scratch}"]
        with tempfile.TemporaryDirectory(prefix="brussels-visual-engine-") as temp:
            engine = Path(temp)
            expected, receipt["engine_hashes"] = engine_checkout(engine, source_commit)
            receipt["expected_asset_hashes"] = expected
            run("just", *boot_options, "luks-boot-qemu-live", args.target)
            monitors[LIVE] = qemu_identity(LIVE)
            with observer(LIVE, "live") as state:
                assert_defaults(state, expected)
                receipt["observations"]["live"] = state
                receipt["frames"]["live-desktop"] = capture(LIVE, out / "live-desktop.png")
            # The shipped frontend autostarts. The shared bounded walkthrough is
            # pre-credential only; the native driver then performs the real install.
            with (out / "walkthrough.tap").open("w") as log:
                run("/usr/bin/python3", str(engine / "scripts/installer-walkthrough.py"), LIVE,
                    str(out), "2", "xfce", "--strict",
                    "--spec=" + str(ROOT / "tests/brussels-installer-screens.yaml"),
                    stdout=log, stderr=subprocess.STDOUT)
            walk = json.loads((out / "walkthrough-xfce.json").read_text())
            if (walk.get("ocr") is not True or walk.get("failures")
                    or not all(walk.get("screens", {}).get(name) is True for name in ("welcome", "disk"))):
                raise RuntimeError("Shared walkthrough did not prove every required pre-credential page")
            receipt["gui_install"] = modules["gui"].install(LIVE, out, passphrase)
            required_stages = {"welcome", "disk", "encryption", "summary", "progress", "completion"}
            if not required_stages.issubset(set(receipt["gui_install"]["stages"])):
                raise RuntimeError("Actual GUI installation did not execute every required stage")
            if not receipt["gui_install"].get("source_revision") or not receipt["gui_install"].get("flatpak_commit"):
                raise RuntimeError("Actual installed frontend source identity is missing")
            hmp(LIVE, "quit")
            deadline = time.monotonic() + 15
            while Path(LIVE).exists() and time.monotonic() < deadline:
                time.sleep(.2)
            if Path(LIVE).exists():
                raise RuntimeError("Live QEMU did not stop before the installed boot")
            receipt["cleanup"][LIVE] = "stopped"
            run("just", *boot_options, "luks-boot-qemu-installed", args.target)
            monitors[INSTALLED] = qemu_identity(INSTALLED)

            def safe_session():
                # Normal GDM keyboard selection of the shipped sole user; no
                # autologin, PAM, preference, or account changes are made.
                hmp(INSTALLED, "sendkey ret")
                time.sleep(4)
                hmp(INSTALLED, "sendkey ret")
                time.sleep(6)
                with observer(INSTALLED, "installed") as state:
                    if state["boot_id"] == receipt["observations"]["live"]["boot_id"]:
                        raise RuntimeError("Installed session is not on a new boot")
                    assert_defaults(state, expected)
                    assert_encrypted_root(state)
                    assert_installed_identity(state, qualification["payload_image"])
                    receipt["capture_state"] = "admitted-active-user-session"
                    receipt["observations"]["installed"] = state
                    receipt["frames"]["installed-desktop"] = capture(INSTALLED, out / "installed-desktop.png")

            receipt["capture_state"] = "secret-blackout"
            modules["unlock"].run_qemu(INSTALLED, passphrase, SERIAL, safe_session=safe_session)
            run("convert", "/tmp/luks-screenshot-plymouth.ppm", str(out / "luks-before-secret.png"))
            receipt["frames"]["luks-before-secret"] = {
                "path": "luks-before-secret.png", "sha256": sha(out / "luks-before-secret.png"),
                "qemu": monitors[INSTALLED], "stage": "pre-secret"}
            with observer(INSTALLED, "about") as state:
                installed = receipt["observations"]["installed"]
                if state["boot_id"] != installed["boot_id"] or state["session"]["id"] != installed["session"]["id"]:
                    raise RuntimeError("About is not in the admitted installed user session")
                if state.get("resolved_logo_sha256") != expected["/usr/share/icons/hicolor/scalable/apps/brussels-logo.svg"]:
                    raise RuntimeError("About icon theme did not resolve the canonical Brussels mark")
                receipt["observations"]["about"] = state
                receipt["frames"]["installed-about"] = capture(INSTALLED, out / "installed-about.png")
            with (out / "install-checkpoints.tap").open("w") as log:
                run("/usr/bin/python3", str(engine / "scripts/install-checkpoints.py"), str(out),
                    "--flavor", "xfce", "--variant", "brussels", "--strict", "--spec",
                    str(ROOT / "tests/brussels-pipeline-screens.yaml"), stdout=log, stderr=subprocess.STDOUT)
            summary = json.loads((out / "install-checkpoints-xfce.json").read_text())
            if not admit_checkpoints(summary) or not (out / "install-checkpoints-xfce.png").is_file():
                raise RuntimeError("Shared visual engine report/contact sheet did not qualify")
            receipt["branding_qualified"] = True
    except BaseException as error:
        receipt["failure"] = type(error).__name__ + ": " + str(error)
        raise
    finally:
        # No screenshots, recorder, failure frames, or secret recipes in cleanup.
        for monitor, identity in reversed(list(monitors.items())):
            try:
                if receipt["cleanup"].get(monitor) == "stopped":
                    continue
                if Path(monitor).exists() and qemu_identity(monitor) == identity:
                    hmp(monitor, "quit")
                deadline = time.monotonic() + 15
                while Path(f"/proc/{identity['pid']}").exists() and time.monotonic() < deadline:
                    time.sleep(.2)
                if Path(f"/proc/{identity['pid']}").exists():
                    raise RuntimeError("Owned QEMU survived bounded cleanup")
                receipt["cleanup"][monitor] = "stopped"
            except Exception as error:
                receipt["cleanup"][monitor] = str(error)
                receipt["branding_qualified"] = False
        for path in (out / "installed.qcow2", out / "scratch.img"):
            path.unlink(missing_ok=True)
        (out / "journey.json").write_text(json.dumps(receipt, indent=2) + "\n")
        if any(value != "stopped" for value in receipt["cleanup"].values()):
            raise RuntimeError("Native visual run did not clean up its owned QEMU processes")


if __name__ == "__main__":
    main()
