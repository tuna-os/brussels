"""The nightly build must not repeat a red night on unchanged inputs, and the
skipped night must never read as a successful build.

promote-stable, staleness-check and build-iso (workflow_run) all treat a
successful run of "Build xfce-linux (Multi-Runner)" as "a fresh image exists at
that commit", so the gate cancels its own run instead of letting it finish
green. Pure source inspection plus the gate script run against a fake `gh`.
"""

import os
import stat
import subprocess
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
WORKFLOW = yaml.safe_load((REPO / ".github/workflows/build-multirunner.yml").read_text())
SHA = "a" * 40


def gate_script() -> str:
    step = next(s for s in WORKFLOW["jobs"]["gate"]["steps"] if s.get("id") == "prev")
    return step["run"]


def run_gate(tmp_path, event, previous, cancel_ok=True):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "gh.log"
    out = tmp_path / "output"
    out.write_text("")
    gh = bin_dir / "gh"
    gh.write_text(
        "#!/bin/sh\n"
        f'echo "$@" >> {log}\n'
        'case "$1" in\n'
        f'  api) printf "%s" "{previous}" ;;\n'
        f'  run) exit {0 if cancel_ok else 1} ;;\n'
        "esac\n"
    )
    sleep = bin_dir / "sleep"
    sleep.write_text("#!/bin/sh\nexit 0\n")
    for tool in (gh, sleep):
        tool.chmod(tool.stat().st_mode | stat.S_IEXEC)
    env = {
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
        "GH_TOKEN": "x", "EVENT": event, "REPO": "tuna-os/brussels",
        "HEAD_SHA": SHA, "RUN_ID": "42", "GITHUB_OUTPUT": str(out),
    }
    subprocess.run(["bash", "-c", gate_script()], env=env, check=True, capture_output=True, text=True)
    calls = log.read_text().splitlines() if log.exists() else []
    return out.read_text().split(), calls


def test_a_manual_dispatch_always_builds(tmp_path):
    outputs, calls = run_gate(tmp_path, "workflow_dispatch", f"failure\t{SHA}")
    assert outputs == ["skip=false"] and calls == []


def test_a_red_night_at_the_same_commit_cancels_the_run(tmp_path):
    outputs, calls = run_gate(tmp_path, "schedule", f"failure\t{SHA}")
    assert any(call.startswith("run cancel 42") for call in calls)
    assert outputs[0] == "skip=true"
    # The shimmed sleep returns at once; a real cancel kills the job there. If it
    # did not, the last write wins and the build proceeds.
    assert outputs[-1] == "skip=false"


def test_a_new_commit_builds_even_after_a_red_night(tmp_path):
    outputs, calls = run_gate(tmp_path, "schedule", f"failure\t{'b' * 40}")
    assert outputs == ["skip=false"] and not any(c.startswith("run cancel") for c in calls)


def test_a_previous_night_that_was_skipped_or_green_builds(tmp_path):
    for conclusion in ("cancelled", "success"):
        sub = tmp_path / conclusion
        sub.mkdir()
        outputs, calls = run_gate(sub, "schedule", f"{conclusion}\t{SHA}")
        assert outputs == ["skip=false"] and not any(c.startswith("run cancel") for c in calls)


def test_a_failed_cancel_builds_instead_of_skipping_green(tmp_path):
    outputs, _ = run_gate(tmp_path, "schedule", f"failure\t{SHA}", cancel_ok=False)
    assert outputs == ["skip=false"]


def test_the_build_waits_for_the_gate_and_cannot_run_on_a_cancelled_one():
    jobs = WORKFLOW["jobs"]
    assert jobs["multirunner"]["needs"] == "gate"
    assert "needs.gate.outputs.skip != 'true'" in jobs["multirunner"]["if"]
    final = jobs["build_final"]
    assert set(final["needs"]) == {"gate", "multirunner"}
    assert "needs.gate.result == 'success'" in final["if"]
    assert "needs.gate.outputs.skip != 'true'" in final["if"]
    assert jobs["gate"]["permissions"]["actions"] == "write"
