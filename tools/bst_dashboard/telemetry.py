"""Host and container telemetry readers for the BuildStream dashboard.

These functions read kernel interfaces and parse Podman output. They keep no
dashboard state and start no threads, so the sampler loop and the tests can
call them directly.
"""

from __future__ import annotations

import os

CPU_HWMON_NAMES = ("coretemp", "k10temp", "zenpower", "cpu_thermal")
CPU_HWMON_LABELS = ("Package", "Tdie", "Tccd")
CPU_THERMAL_ZONE_TYPES = ("cpu", "x86", "acpitz")

_MEM_SUFFIXES = (("GiB", 1 << 30), ("MiB", 1 << 20), ("kB", 1000))


def read_proc_stat(path: str = "/proc/stat") -> list[tuple[int, int]]:
    """Return a list of (idle_ticks, total_ticks), first entry is aggregate."""
    stats = []
    try:
        with open(path) as f:
            for line in f:
                if not line.startswith("cpu"):
                    break
                parts = line.split()
                # cpu  user nice system idle iowait irq softirq ...
                vals = list(map(int, parts[1:8]))
                idle = vals[3] + vals[4]
                total = sum(vals)
                stats.append((idle, total))
    except Exception:
        pass
    return stats


def read_proc_meminfo(path: str = "/proc/meminfo") -> tuple[int, int]:
    """Return (used_bytes, total_bytes) from /proc/meminfo."""
    info: dict[str, int] = {}
    with open(path) as f:
        for line in f:
            k, v = line.split(":", 1)
            info[k.strip()] = int(v.split()[0])  # kB
    total = info.get("MemTotal", 0)
    avail = info.get("MemAvailable", 0)
    return (total - avail) * 1024, total * 1024


def cpu_percentages(
    prev: list[tuple[int, int]], cur: list[tuple[int, int]]
) -> list[float]:
    """Return busy percentage per entry between two read_proc_stat() samples."""
    pcts = []
    for (idle, total), (prev_idle, prev_total) in zip(cur, prev):
        d_total = total - prev_total
        pct = round(100.0 * (1.0 - (idle - prev_idle) / d_total), 1) if d_total else 0.0
        pcts.append(max(0.0, min(100.0, pct)))
    return pcts


def parse_podman_stats(output: str) -> tuple[float | None, int | None]:
    """Parse `podman stats --format "{{.CPUPerc}},{{.MemUsage}}"` output.

    Return (cpu_pct, mem_bytes), or (None, None) when the output is empty or
    malformed.
    """
    try:
        line = output.strip()
        if not line:
            return None, None
        cpu_str, mem_str = line.split(",", 1)
        cpu = float(cpu_str.strip().rstrip("%"))
        # mem_str like "1.23GiB / 31.7GiB" — grab the used part
        mem_used_str = mem_str.split("/")[0].strip()
        mul = 1
        for suffix, factor in _MEM_SUFFIXES:
            if mem_used_str.endswith(suffix):
                mul = factor
                mem_used_str = mem_used_str[: -len(suffix)]
                break
        return cpu, int(float(mem_used_str) * mul)
    except Exception:
        return None, None


def read_cpu_temp(
    hwmon_base: str = "/sys/class/hwmon",
    thermal_base: str = "/sys/class/thermal",
) -> float | None:
    """Return CPU package temperature in °C from hwmon or thermal_zone, or None."""
    try:
        for hwmon_dir in sorted(os.listdir(hwmon_base)):
            hwmon_path = os.path.join(hwmon_base, hwmon_dir)
            try:
                with open(os.path.join(hwmon_path, "name")) as f:
                    name = f.read().strip()
            except Exception:
                continue
            if name not in CPU_HWMON_NAMES:
                continue
            # Prefer a sensor labelled "Package id 0", "Tdie", or "Tccd"
            best = None
            for fname in sorted(os.listdir(hwmon_path)):
                if not (fname.startswith("temp") and fname.endswith("_input")):
                    continue
                label = ""
                try:
                    with open(os.path.join(hwmon_path, fname.replace("_input", "_label"))) as f:
                        label = f.read().strip()
                except Exception:
                    pass
                try:
                    with open(os.path.join(hwmon_path, fname)) as f:
                        val = int(f.read().strip()) / 1000.0
                except Exception:
                    continue
                if any(k in label for k in CPU_HWMON_LABELS):
                    return val  # best match — return immediately
                if best is None:
                    best = val  # fall back to first sensor in this hwmon
            if best is not None:
                return best
    except Exception:
        pass
    # Fallback: thermal_zone
    try:
        for zone_dir in sorted(os.listdir(thermal_base)):
            if not zone_dir.startswith("thermal_zone"):
                continue
            zone_path = os.path.join(thermal_base, zone_dir)
            try:
                with open(os.path.join(zone_path, "type")) as f:
                    tz_type = f.read().strip().lower()
                if any(k in tz_type for k in CPU_THERMAL_ZONE_TYPES):
                    with open(os.path.join(zone_path, "temp")) as f:
                        return int(f.read().strip()) / 1000.0
            except Exception:
                continue
    except Exception:
        pass
    return None
