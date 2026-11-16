#!/usr/bin/env python3
"""BuildStream live build dashboard.

Tails a BST build log and serves a live HTML dashboard.

Usage:
    python3 bst-dashboard.py [OPTIONS]

Options:
    --log FILE        Build log to tail (default: $BST_LOG or /var/tmp/bst-build.log)
    --port PORT       HTTP port (default: $BST_DASHBOARD_PORT or 8765)
    --target TARGET   BST element to build via the Start button (default: $BST_TARGET or oci/aurora.bst)
    --project DIR     Project source directory mounted into container (default: $BST_PROJECT or script dir)
    --bst-image IMAGE BST2 container image (default: $BST2_IMAGE or auto-detect from running container)
    --help            Show this message
"""

import os
import sys
import time
import json
import argparse
import datetime
import threading
import subprocess
import multiprocessing
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn

try:
    from tools.bst_dashboard import telemetry
    from tools.bst_dashboard.deptree import parse_bst_show_deps
    from tools.bst_dashboard.model import State
    from tools.bst_dashboard.parser import (
        ANSI,
        CMAKE_PROGRESS_RE,
        RUST_COMPILE_RE,
        RUST_FINISHED_RE,
        parse_line as _parse_line,
        reset_state as _reset_state,
    )
except ModuleNotFoundError:
    from bst_dashboard import telemetry
    from bst_dashboard.deptree import parse_bst_show_deps
    from bst_dashboard.model import State
    from bst_dashboard.parser import (
        ANSI,
        CMAKE_PROGRESS_RE,
        RUST_COMPILE_RE,
        RUST_FINISHED_RE,
        parse_line as _parse_line,
        reset_state as _reset_state,
    )

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """Handle requests in a separate thread."""
    daemon_threads = True

_DEFAULT_BST2_IMAGE = (
    "registry.gitlab.com/freedesktop-sdk/infrastructure/"
    "freedesktop-sdk-docker-images/bst2:f89b4aef847ef040b345acceda15a850219eb8f1"
)

def _parse_args():
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument("--log",       default=None)
    p.add_argument("--port",      type=int, default=None)
    p.add_argument("--target",    default=None)
    p.add_argument("--project",   default=None)
    p.add_argument("--bst-image", default=None, dest="bst_image")
    p.add_argument("--help", "-h", action="store_true")
    args, _ = p.parse_known_args()
    if args.help:
        print(__doc__)
        sys.exit(0)
    return args

_args = _parse_args()

LOG_FILE    = _args.log       or os.environ.get("BST_LOG",              "/var/tmp/bst-build.log")
PORT        = _args.port      or int(os.environ.get("BST_DASHBOARD_PORT", "8765"))
BST_TARGET  = _args.target    or os.environ.get("BST_TARGET",           "oci/aurora.bst")
PROJECT_DIR = _args.project   or os.environ.get("BST_PROJECT",          os.path.dirname(os.path.abspath(__file__)))
BST2_IMAGE  = _args.bst_image or os.environ.get("BST2_IMAGE",           _DEFAULT_BST2_IMAGE)

# ── Build process control ──────────────────────────────────────────────────────
BUILD_LOCK = threading.Lock()
BUILD_PROC: "subprocess.Popen | None" = None

_sysinfo_lock = threading.Lock()
_sysinfo = {"cpu_pct": 0.0, "cpu_cores": [], "mem_used": 0, "mem_total": 0,
            "bst_cpu_pct": None, "bst_mem": None, "cpu_temp": None,
            "bst_running": False}
_cpu_prev: list[tuple[int, int]] = []   # list of (idle_ticks, total_ticks)

def _bst_container_id() -> str:
    """Return container ID of any running BST2 container, or empty string."""
    try:
        result = subprocess.run(
            ["podman", "ps", "-q", "--filter", f"ancestor={BST2_IMAGE}"],
            capture_output=True, text=True, timeout=3,
        )
        return result.stdout.strip()
    except Exception:
        return ""


def build_running() -> bool:
    if BUILD_PROC is not None and BUILD_PROC.poll() is None:
        return True
    with _sysinfo_lock:
        return _sysinfo.get("bst_running", False)


def start_build() -> bool:
    global BUILD_PROC
    with BUILD_LOCK:
        if build_running():
            return False
        nproc = multiprocessing.cpu_count()
        cache_dir = os.path.join(os.path.expanduser("~"), ".cache", "buildstream")
        os.makedirs(cache_dir, exist_ok=True)
        with open(LOG_FILE, "w") as f:
            f.write(f"=== Build started at {datetime.datetime.now().strftime('%c')} ===\n")
        log_f = open(LOG_FILE, "a")
        cmd = [
            "podman", "run", "--rm",
            "--privileged", "--device", "/dev/fuse", "--network=host",
            "-v", f"{PROJECT_DIR}:/src:rw",
            "-v", f"{cache_dir}:/root/.cache/buildstream:rw",
            "-w", "/src",
            BST2_IMAGE,
            "bash", "-c", 'bst --colors "$@"', "--",
            "--max-jobs", str(max(1, nproc // 2)),
            "--fetchers", str(nproc),
            "build", BST_TARGET,
        ]
        BUILD_PROC = subprocess.Popen(cmd, stdout=log_f, stderr=log_f)
        return True


def stop_build() -> bool:
    global BUILD_PROC
    with BUILD_LOCK:
        killed = False
        if BUILD_PROC is not None and BUILD_PROC.poll() is None:
            BUILD_PROC.terminate()
            killed = True
        cid = _bst_container_id()
        if cid:
            try:
                subprocess.run(["podman", "stop", cid], timeout=10)
                killed = True
            except Exception:
                pass
        return killed



STATE = State(build_running=build_running, sysinfo=lambda: _sysinfo)


def reset_state():
    _reset_state(STATE)


def parse_line(raw: str):
    _parse_line(raw, STATE)

# ── cmake progress enrichment ──────────────────────────────────────────────────

def _enrich_cmake(snap: dict):
    """Read last 8 KB of each active job's log and inject build progress info.

    Sets one of:
      cmake_done / cmake_total  — cmake/ninja/meson [x/y] markers
      rust_crates               — count of Rust "Compiling" lines seen
    """
    for job in snap.get("active", []):
        log_path = job.get("log", "")
        if not log_path:
            continue
        try:
            size = os.path.getsize(log_path)
            with open(log_path, "rb") as f:
                f.seek(max(0, size - 8192))
                tail = f.read().decode("utf-8", errors="replace")
            # cmake / ninja / meson: prefer [x/y] markers (most reliable)
            matches = CMAKE_PROGRESS_RE.findall(tail)
            if matches:
                done_s, total_s = matches[-1]
                job["cmake_done"]  = int(done_s)
                job["cmake_total"] = int(total_s)
                continue
            # Rust/cargo: count "Compiling" lines in the tail
            rust_lines = RUST_COMPILE_RE.findall(tail)
            if rust_lines:
                job["rust_crates"] = len(rust_lines)
                job["rust_done"]   = not bool(RUST_FINISHED_RE.search(tail))
        except Exception:
            pass

# ── Dependency tree ────────────────────────────────────────────────────────────

_deptree_lock = threading.Lock()
_deptree: dict = {"status": "idle", "nodes": {}, "root": ""}


def _fetch_deptree():
    """Run bst show in the BST container and populate _deptree (background thread)."""
    global _deptree
    with _deptree_lock:
        if _deptree["status"] == "loading":
            return   # already in progress
        _deptree = {"status": "loading", "nodes": {}, "root": BST_TARGET}

    try:
        cache_dir = os.path.join(os.path.expanduser("~"), ".cache", "buildstream")
        result = subprocess.run(
            [
                "podman", "run", "--rm",
                "--privileged", "--device", "/dev/fuse", "--network=host",
                "-v", f"{PROJECT_DIR}:/src:rw",
                "-v", f"{cache_dir}:/root/.cache/buildstream:rw",
                "-w", "/src",
                BST2_IMAGE,
                "bst", "show", "--deps", "all",
                "--format", "%{name}\t%{deps}\n",
                BST_TARGET,
            ],
            capture_output=True, text=True, timeout=300,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip()[-500:] or "bst show failed")
        nodes = parse_bst_show_deps(result.stdout)

        with _deptree_lock:
            _deptree = {"status": "ready", "nodes": nodes, "root": BST_TARGET}
    except Exception as exc:
        with _deptree_lock:
            _deptree = {"status": "error", "nodes": {}, "root": BST_TARGET,
                        "error": str(exc)[:500]}

# ── System resource sampling ───────────────────────────────────────────────────

_read_proc_stat = telemetry.read_proc_stat
_read_proc_meminfo = telemetry.read_proc_meminfo
_get_cpu_temp = telemetry.read_cpu_temp


def _bst_container_stats(cid: str) -> tuple[float | None, int | None]:
    """Return (cpu_pct, mem_bytes) for the running BST container, or (None, None)."""
    if not cid:
        return None, None
    try:
        r = subprocess.run(
            ["podman", "stats", "--no-stream", "--format",
             "{{.CPUPerc}},{{.MemUsage}}", cid],
            capture_output=True, text=True, timeout=3,
        )
    except Exception:
        return None, None
    return telemetry.parse_podman_stats(r.stdout)


def _sysinfo_sampler():
    global _cpu_prev
    while True:
        try:
            stats = _read_proc_stat()
            if not _cpu_prev or len(_cpu_prev) != len(stats):
                _cpu_prev = stats
                time.sleep(1)
                continue

            cpu_pcts = telemetry.cpu_percentages(_cpu_prev, stats)
            _cpu_prev = stats

            mem_used, mem_total = _read_proc_meminfo()
            cid = _bst_container_id()
            bst_cpu, bst_mem = _bst_container_stats(cid) if cid else (None, None)
            cpu_temp = _get_cpu_temp()

            with _sysinfo_lock:
                _sysinfo["cpu_pct"]     = cpu_pcts[0]
                _sysinfo["cpu_cores"]   = cpu_pcts[1:]
                _sysinfo["mem_used"]    = mem_used
                _sysinfo["mem_total"]   = mem_total
                _sysinfo["bst_cpu_pct"] = bst_cpu
                _sysinfo["bst_mem"]     = bst_mem
                _sysinfo["cpu_temp"]    = cpu_temp
                _sysinfo["bst_running"] = bool(cid)
        except Exception:
            pass
        time.sleep(2)


threading.Thread(target=_sysinfo_sampler, daemon=True).start()



def tail_log():
    """Tail LOG_FILE, resetting state if the file is truncated (new build started)."""
    buf = ""
    pos = 0
    while True:
        try:
            size = os.path.getsize(LOG_FILE)
        except FileNotFoundError:
            time.sleep(2)
            continue

        if size < pos:
            # File was truncated — new build started
            reset_state()
            pos = 0
            buf = ""

        if size > pos:
            try:
                with open(LOG_FILE, "rb") as f:
                    f.seek(pos)
                    chunk = f.read(size - pos).decode("utf-8", errors="replace")
                pos = size
                buf += chunk
                lines = buf.split("\n")
                buf = lines[-1]
                for line in lines[:-1]:
                    parse_line(line)
            except Exception:
                pass
        elif STATE.catching_up:
            # We've read everything — mark catch-up complete
            def _done_catching_up(s):
                s.catching_up = False
                # If no active jobs and we have data, use log file mtime as end time
                if not s.active and s.success_count > 0 and not s.build_end_ts:
                    try:
                        s.build_end_ts = os.path.getmtime(LOG_FILE)
                    except Exception:
                        pass
            STATE.update(_done_catching_up)

        time.sleep(0.5)


# ── HTML ───────────────────────────────────────────────────────────────────────

DASHBOARD_HTML_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "bst-dashboard.html"
)
with open(DASHBOARD_HTML_PATH, encoding="utf-8") as dashboard_html:
    HTML = dashboard_html.read()

# ── HTTP handler ───────────────────────────────────────────────────────────────

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # silence access log

    def _json_reply(self, data: dict):
        body = json.dumps(data).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _norm_path(self):
        """Strip /bst prefix so we work both via Caddy and Tailscale Serve directly."""
        p = self.path.split("?", 1)
        path = p[0].rstrip("/") or "/"
        query = p[1] if len(p) > 1 else ""
        if path.startswith("/bst"):
            path = path[4:] or "/"
        return path, query

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        self.rfile.read(length)
        path, _ = self._norm_path()
        if path == "/api/start":
            ok = start_build()
            self._json_reply({"ok": ok})
        elif path == "/api/stop":
            ok = stop_build()
            self._json_reply({"ok": ok})
        elif path == "/api/deptree/refresh":
            threading.Thread(target=_fetch_deptree, daemon=True).start()
            self._json_reply({"ok": True})
        else:
            self.send_response(404)
            self.end_headers()

    def do_GET(self):
        path, query = self._norm_path()
        if path == "/api/state":
            snap = STATE.snapshot()
            _enrich_cmake(snap)
            data = json.dumps(snap).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)
        elif path == "/api/deptree":
            with _deptree_lock:
                payload = dict(_deptree)
            # Auto-trigger fetch if idle
            if payload["status"] == "idle":
                threading.Thread(target=_fetch_deptree, daemon=True).start()
                payload["status"] = "loading"
            data = json.dumps(payload).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)
        elif path == "/api/log":
            import urllib.parse
            params = dict(p.split("=", 1) for p in query.split("&") if "=" in p)
            log_path = None
            if "path" in params:
                # Direct path (for failures) — validate it stays inside buildstream logs
                candidate = urllib.parse.unquote(params["path"])
                bst_logs = os.path.expanduser("~/.cache/buildstream/logs")
                if os.path.abspath(candidate).startswith(bst_logs):
                    log_path = candidate
            elif "hash" in params:
                h = params["hash"]
                with STATE._lock:
                    entry = STATE.active.get(h)
                    if entry:
                        log_path = entry.get("log")
            if not log_path or not os.path.exists(log_path):
                body = b"Log not available"
                self.send_response(404)
            else:
                try:
                    with open(log_path, "rb") as f:
                        raw = f.read().decode("utf-8", errors="replace")
                    lines = ANSI.sub("", raw).splitlines()[-300:]
                    body = "\n".join(lines).encode()
                    self.send_response(200)
                except Exception as e:
                    body = str(e).encode()
                    self.send_response(500)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
        else:
            body = HTML.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)


# ── Main ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    tailer = threading.Thread(target=tail_log, daemon=True)
    tailer.start()

    server = ThreadedHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"BST Dashboard  http://localhost:{PORT}/")
    print(f"  log:     {LOG_FILE}")
    print(f"  target:  {BST_TARGET}")
    print(f"  project: {PROJECT_DIR}")
    print(f"  image:   {BST2_IMAGE[:60]}…" if len(BST2_IMAGE) > 60 else f"  image:   {BST2_IMAGE}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
