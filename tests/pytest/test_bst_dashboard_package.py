"""Contract tests for reusable BuildStream dashboard components."""

from tools.bst_dashboard import telemetry
from tools.bst_dashboard.deptree import parse_bst_show_deps
from tools.bst_dashboard.model import State
from tools.bst_dashboard.parser import parse_line


def event(status, *, build_hash="abcdef"):
    return (
        f"[00:00:01][{build_hash}][build:xfce-linux/session.bst] "
        f"{status:<7} xfce/session/{build_hash}-build.log"
    )


def test_parser_updates_injected_state_without_dashboard_runtime():
    state = State()

    parse_line(event("START"), state)
    parse_line(event("SUCCESS"), state)

    assert state.active == {}
    assert state.success_count == 1
    assert state.completed[0]["element"] == "xfce-linux/session.bst"


def test_state_snapshot_uses_injected_runtime_adapters():
    state = State(
        build_running=lambda: True,
        sysinfo=lambda: {"cpu_pct": 42.0},
    )

    snapshot = state.snapshot()

    assert snapshot["build_running"] is True
    assert snapshot["sysinfo"] == {"cpu_pct": 42.0}


def test_deptree_parser_reads_bst_show_block_sequences():
    output = (
        "root.bst\t- a.bst\n"
        "- b.bst\n"
        "a.bst\t[]\n"
        "b.bst\t- a.bst\n"
    )

    assert parse_bst_show_deps(output) == {
        "root.bst": ["a.bst", "b.bst"],
        "a.bst": [],
        "b.bst": ["a.bst"],
    }


def test_deptree_parser_ignores_lines_before_first_element():
    assert parse_bst_show_deps("- stray.bst\nonly.bst\t[]\n") == {"only.bst": []}


def test_proc_readers_take_explicit_paths(tmp_path):
    stat = tmp_path / "stat"
    stat.write_text("cpu  1 2 3 4 5 6 7\ncpu0 1 1 1 1 1 1 1\nintr 0\n")
    meminfo = tmp_path / "meminfo"
    meminfo.write_text("MemTotal:       1000 kB\nMemAvailable:    400 kB\n")

    assert telemetry.read_proc_stat(str(stat)) == [(9, 28), (2, 7)]
    assert telemetry.read_proc_meminfo(str(meminfo)) == (600 * 1024, 1000 * 1024)
    assert telemetry.read_proc_stat(str(tmp_path / "missing")) == []


def test_cpu_percentages_clamps_and_handles_idle_interval():
    prev = [(100, 200), (50, 100), (10, 10)]
    cur = [(150, 400), (50, 100), (10, 20)]

    assert telemetry.cpu_percentages(prev, cur) == [75.0, 0.0, 100.0]


def test_podman_stats_parser_rejects_empty_and_malformed_output():
    assert telemetry.parse_podman_stats("12.5%,1.50GiB / 31.7GiB\n") == (12.5, int(1.5 * (1 << 30)))
    assert telemetry.parse_podman_stats("") == (None, None)
    assert telemetry.parse_podman_stats("not-stats") == (None, None)


def test_cpu_temp_prefers_package_label_then_thermal_zone(tmp_path):
    hwmon = tmp_path / "hwmon"
    sensor = hwmon / "hwmon0"
    sensor.mkdir(parents=True)
    (sensor / "name").write_text("coretemp\n")
    (sensor / "temp1_input").write_text("41000\n")
    (sensor / "temp2_input").write_text("55000\n")
    (sensor / "temp2_label").write_text("Package id 0\n")
    thermal = tmp_path / "thermal"
    zone = thermal / "thermal_zone0"
    zone.mkdir(parents=True)
    (zone / "type").write_text("x86_pkg_temp\n")
    (zone / "temp").write_text("60000\n")

    assert telemetry.read_cpu_temp(str(hwmon), str(thermal)) == 55.0
    assert telemetry.read_cpu_temp(str(tmp_path / "none"), str(thermal)) == 60.0
    assert telemetry.read_cpu_temp(str(tmp_path / "none"), str(tmp_path / "none")) is None
