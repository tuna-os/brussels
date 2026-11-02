#!/usr/bin/env python3
"""Read the existing graphical session; never set preferences or create a session.

The native VM adapter supplies only the one-boot loopback endpoint and stage.
Expected identity, settings and asset hashes stay on the host.
"""
import hashlib
import json
import os
from pathlib import Path
import pwd
import subprocess
import time
import urllib.request


def command(*args):
    return subprocess.check_output(args, text=True, timeout=15).strip()


def digest(path):
    with open(path, "rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def observe():
    uid = os.getuid()
    sessions = json.loads(command("loginctl", "list-sessions", "--json=short"))
    active = []
    for session in sessions:
        if int(session["uid"]) != uid:
            continue
        properties = dict(line.split("=", 1) for line in command(
            "loginctl", "show-session", session["session"],
            "-p", "Active", "-p", "Class", "-p", "Type", "-p", "User", "-p", "State",
        ).splitlines())
        if (properties.get("Active") == "yes" and properties.get("Class") == "user"
                and properties.get("Type") in ("wayland", "x11")):
            active.append({"id": session["session"], **properties})
    if len(active) != 1:
        raise RuntimeError("Exactly one active graphical user session is required")
    assets = {}
    for path in (
        "/usr/share/backgrounds/TunaOS/Brussels/brussels-wallpaper.png",
        "/usr/share/icons/hicolor/scalable/apps/brussels-logo.svg",
        "/usr/share/tunaos/branding/xfce-linux-wordmark.svg",
    ):
        try:
            assets[path] = digest(path)
        except OSError as error:
            assets[path] = {"error": str(error)}
    mounts = {}
    for mount in ("/", "/sysroot"):
        try:
            mounts[mount] = json.loads(command("findmnt", "--json", mount))
        except subprocess.CalledProcessError:
            mounts[mount] = None
    bootc = json.loads(command("bootc", "status", "--json"))
    return {
        "boot_id": Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
        "uid": uid, "user": pwd.getpwuid(uid).pw_name, "session": active[0],
        "os_release": Path("/etc/os-release").read_text(),
        "xfconf": command("xfconf-query", "-c", "xfce4-desktop", "-lv"),
        "root_mounts": mounts,
        "block_devices": json.loads(command("lsblk", "--json", "-o", "NAME,TYPE,FSTYPE,UUID")),
        "bootc": bootc,
        "observed_monotonic": time.monotonic(),
        "assets": assets,
    }


def post(endpoint, suffix, record):
    request = urllib.request.Request(endpoint + suffix, data=json.dumps(record).encode(),
                                     headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=15) as response:
        response.read()


def main(endpoint, stage):
    about = None
    record = {"stage": stage, "observed_at": time.time()}
    try:
        record.update(observe())
        if stage == "about":
            about = subprocess.Popen(["xfce4-about"], stdout=subprocess.DEVNULL,
                                     stderr=subprocess.DEVNULL, start_new_session=True)
            time.sleep(3)
            if about.poll() is not None:
                raise RuntimeError("The shipped xfce4-about UI did not remain active")
            record["about_pid"] = about.pid
            record["about_start_ticks"] = Path(f"/proc/{about.pid}/stat").read_text().split(") ", 1)[1].split()[19]
            try:
                import gi
                gi.require_version("Gtk", "3.0")
                from gi.repository import Gtk
                if not Gtk.init_check()[0]:
                    raise RuntimeError("Cannot inspect the existing GTK icon theme")
                icon = Gtk.IconTheme.get_default().lookup_icon("brussels-logo", 64, 0)
                record["resolved_logo"] = icon.get_filename()
                record["resolved_logo_sha256"] = digest(record["resolved_logo"])
            except Exception as error:
                record["logo_resolution_error"] = str(error)
        post(endpoint, "/receipt", record)
        if about:
            with urllib.request.urlopen(endpoint + "/done", timeout=45) as response:
                response.read()
    except Exception as error:
        post(endpoint, "/receipt", {"stage": stage, "error": str(error)})
        raise
    finally:
        if about:
            import signal
            os.killpg(about.pid, signal.SIGTERM)
            try:
                about.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(about.pid, signal.SIGKILL)
                about.wait(timeout=5)
            post(endpoint, "/cleanup", {"stage": stage, "about_stopped": about.poll() is not None})
