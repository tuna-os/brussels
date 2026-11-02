"""Invariants across the live-ISO build scripts.

Each assertion here encodes a bug class that actually shipped (see
docs/ci-and-iso-pipeline.md troubleshooting table). Cheap to run, no
containers needed — pure source inspection.
"""

import os
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TARGET = "xfce-linux"
INSTALLER_APP = "org.tunaos.InstallerXfce"
READY_MARKER = "XFCE_LINUX_LIVE_READY"

SRC = REPO / TARGET / "src"
INSTALL_FLATPAKS = (SRC / "install-flatpaks.sh").read_text()
CONFIGURE_LIVE = (SRC / "configure-live.sh").read_text()
CONTAINERFILE = (REPO / TARGET / "Containerfile").read_text()


def test_installer_app_id_consistent():
    """install-flatpaks.sh and configure-live.sh must bake and wire the SAME
    installer app ID — they once drifted apart and the installer never
    launched (autostart + fisherman symlink pointed at an uninstalled app)."""
    assert INSTALLER_APP in INSTALL_FLATPAKS
    assert INSTALLER_APP in CONFIGURE_LIVE
    for stale in ("org.bootcinstaller.Installer", "org.xfceinstaller"):
        assert stale not in INSTALL_FLATPAKS, f"stale installer id {stale} in install-flatpaks.sh"
        assert stale not in CONFIGURE_LIVE.replace(
            # the polkit action id is shared and fine
            "org.tunaos.Installer.install", ""
        ), f"stale installer id {stale} in configure-live.sh"


def test_live_ready_marker_present():
    """CI's boot gate greps the serial log for the ready marker; if
    configure-live.sh stops printing it every ISO 'fails' to boot."""
    assert READY_MARKER in CONFIGURE_LIVE


def test_payload_ref_points_at_our_image():
    ref = (REPO / TARGET / "payload_ref").read_text().strip()
    assert ref.startswith(f"ghcr.io/tuna-os/{TARGET}:"), ref


def test_polkit_action_id_is_shared_constant():
    """All four frontends escalate via the shared action id; renaming it
    breaks every installer at once."""
    assert "org.tunaos.Installer.install" in CONFIGURE_LIVE


def test_fisherman_symlink_target():
    """Frontends run `pkexec /usr/local/bin/fisherman`; the symlink must be
    created and the polkit annotate path must match."""
    assert "/usr/local/bin/fisherman" in CONFIGURE_LIVE
    assert re.search(r"annotate.*exec\.path.*>/usr/local/bin/fisherman<", CONFIGURE_LIVE)


def test_containerfile_wires_this_targets_dracut_module():
    assert f"95{TARGET}-isofile" in CONTAINERFILE
    module_dir = REPO / TARGET / "src" / "dracut" / f"95{TARGET}-isofile"
    assert (module_dir / "module-setup.sh").exists()
    setup = (module_dir / "module-setup.sh").read_text()
    hook = re.search(r'inst_hook initqueue \d+ "\$moddir/([^"]+)"', setup)
    assert hook, "module-setup.sh must install an initqueue hook"
    assert (module_dir / hook.group(1)).exists(), f"hook script {hook.group(1)} missing"


def test_single_root_justfile():
    """just >=1.30 hard-errors when both justfile and Justfile exist — this
    killed every CI invocation once. Extra recipes belong in iso.justfile."""
    assert (REPO / "Justfile").exists()
    assert not (REPO / "justfile").exists(), "second root justfile reintroduced"
    assert 'import "iso.justfile"' in (REPO / "Justfile").read_text()


def test_gitignore_does_not_swallow_target_containerfile():
    """An unanchored 'Containerfile' rule once silently dropped
    <target>/Containerfile from the repo."""
    gitignore = (REPO / ".gitignore").read_text() if (REPO / ".gitignore").exists() else ""
    for line in gitignore.splitlines():
        line = line.strip()
        assert line != "Containerfile", (
            "unanchored Containerfile gitignore rule — use /Containerfile"
        )


def test_no_quiet_karg_in_elements():
    """CI serial-log assertions depend on boot messages; a kargs.d drop-in
    adding 'quiet' would blind every boot gate."""
    for bst in (REPO / "elements").rglob("*.bst"):
        text = bst.read_text()
        if "kargs.d" in text:
            assert '"quiet"' not in text, f"{bst} adds quiet karg"


def test_automatic_checks_and_iso_builds_preserve_every_run():
    """Shared groups evict pending runs even with cancel-in-progress false.

    Preserve automatic triggers with run IDs; only PR updates and manual ISO
    reruns may supersede work. Lint is part of the Test workflow.
    """
    workflows = REPO / ".github" / "workflows"
    cases = {
        "test.yml": (
            "${{ github.workflow }}-${{ github.event.pull_request.number || github.run_id }}",
            "${{ github.event_name == 'pull_request' }}",
        ),
        "build-iso.yml": (
            "${{ github.workflow }}-${{ github.event_name }}-"
            "${{ github.event_name == 'workflow_dispatch' && github.ref_name || github.run_id }}",
            "${{ github.event_name == 'workflow_dispatch' }}",
        ),
    }
    for name, (group, cancel) in cases.items():
        text = (workflows / name).read_text()
        assert f"  group: {group}\n" in text, name
        assert f"  cancel-in-progress: {cancel}\n" in text, name


def test_image_publish_cancels_superseded_runs():
    text = (REPO / ".github/workflows/build-and-publish-xfce-linux.yml").read_text()
    assert "concurrency:" in text
    assert re.search(r"^  cancel-in-progress: true$", text, re.MULTILINE)


def test_scheduled_multirunner_preserves_in_progress_builds():
    """The multi-hour scheduled build must queue instead of discarding work."""
    workflow = (REPO / ".github" / "workflows" / "build-multirunner.yml").read_text()

    assert not re.search(r"^\s*push:\s*(?:#.*)?$", workflow, re.MULTILINE)
    assert re.search(
        r"^\s*cancel-in-progress:\s*false\s*(?:#.*)?$", workflow, re.MULTILINE
    )


def test_chained_iso_requires_successful_image_build():
    """Failed/cancelled image builds must not launch an ISO against stale tags."""
    workflow = (REPO / ".github/workflows/build-iso.yml").read_text()
    job = workflow.split("  build-and-publish:\n", 1)[1].split("    steps:", 1)[0]
    guard = re.search(r"    if: >-\n((?:      .*\n)+)", job)
    assert guard, "guard the job before allocating a runner"
    assert " ".join(guard.group(1).split()) == (
        "github.event_name != 'workflow_run' || "
        "github.event.workflow_run.conclusion == 'success'"
    )


def test_qemu_serial_readers_use_qemu_privileges():
    """Root QEMU can create 0600 logs; unprivileged grep silently times out."""
    recipes = (REPO / "iso.justfile").read_text()
    readers = [
        line.strip() for line in recipes.splitlines()
        if re.search(r"\b(?:grep|tail)\b", line)
        and re.search(r"\{\{(?:luks|plain)-qemu-serial-", line)
    ]
    assert len(readers) >= 6
    for line in readers:
        assert re.search(r"sudo (?:grep|tail)\b", line), line
