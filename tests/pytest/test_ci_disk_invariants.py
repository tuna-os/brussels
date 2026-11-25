"""Invariants that keep the CI jobs inside the runner's disk.

Each assertion encodes a measured incident (see the troubleshooting table in
docs/ci-and-iso-pipeline.md). Scheduled runs 34072176433, 34176106533 and
34298830711 all lost `build_final` to the runner agent's own
"No space left on device", not to a build error: on 2026-09-10 the core plus
ten chunk CAS tarballs measured ~266 GB compressed against a runner disk of
roughly 100-110 GB. Pure source inspection, no containers.
"""

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

MULTIRUNNER = (REPO / ".github/workflows/build-multirunner.yml").read_text()
PR_BUILD = (REPO / ".github/workflows/pr-build-changed.yml").read_text()
BST_CONF = (REPO / "buildstream-ci.conf").read_text()
EXPORT_RECIPE = (REPO / "just/buildstream.just").read_text()
RESTORE_SCRIPT = REPO / "scripts/cas-restore-stream.sh"

# Everything in build_final, from the job key to the end of the file.
BUILD_FINAL = MULTIRUNNER[MULTIRUNNER.index("  build_final:"):]


def test_cas_tarballs_are_streamed_not_pulled():
    """`oras pull -o .` stages the whole tarball (up to 28 GB compressed) on
    the runner before extracting it, beside the cache it unpacks into. Both
    CAS-restoring workflows must stream instead."""
    for name, body in (("build_final", BUILD_FINAL), ("pr-build-changed", PR_BUILD)):
        assert not re.search(r"oras pull\s+\"?ghcr\.io/\$\{REPO_LOWER\}/cache-", body), (
            f"{name} restores CAS with `oras pull`; stream it via "
            "scripts/cas-restore-stream.sh instead"
        )
        assert "cas-restore-stream.sh" in body, f"{name} does not stream its CAS restore"


def test_restore_script_is_executable_and_streams_to_stdout():
    assert RESTORE_SCRIPT.exists(), "scripts/cas-restore-stream.sh is missing"
    assert RESTORE_SCRIPT.stat().st_mode & 0o111, "cas-restore-stream.sh is not executable"
    body = RESTORE_SCRIPT.read_text()
    assert 'python3 "$CAS_TRANSPORT" restore "$REF" "$CACHE_DIR"' in body, (
        "restore script must stream through bst-ci's cas_transport.py restore"
    )
    assert "set -euo pipefail" in body, "a broken pipe must fail the restore, not pass silently"


def test_cas_is_dropped_before_the_image_is_exported():
    """Run 34298830711 built the target in 18 minutes and then died in
    "Export OCI image": the cache and the squashed image do not fit
    together. The artifact checkout must precede the export, and the cache
    must be gone in between."""
    checkout = BUILD_FINAL.index("artifact checkout")
    drop = BUILD_FINAL.index("rm -rf /cache/cas")
    export = BUILD_FINAL.index("just export")
    assert checkout < drop < export, (
        "build_final must check the artifact out, drop the CAS, then export"
    )
    assert "EXPORT_REUSE_CHECKOUT" in BUILD_FINAL, (
        "the export step must tell `just export` not to re-checkout from the deleted cache"
    )


def test_export_recipe_honours_the_reuse_switch():
    """`just export` normally checks the artifact out itself. In CI the cache
    is already deleted by then, so it has to reuse .build-out — and fail
    loudly rather than silently exporting nothing if it is absent."""
    assert "EXPORT_REUSE_CHECKOUT" in EXPORT_RECIPE
    assert re.search(r'if \[ ! -d \.build-out \]', EXPORT_RECIPE), (
        "reuse mode must verify .build-out exists"
    )


def test_buildstream_cache_has_a_quota():
    """Without a quota, each chunk re-tars every stale artifact generation it
    ever restored, which is how the chunk tarballs reached 20-29 GB each."""
    cache_block = BST_CONF[BST_CONF.index("cache:"):]
    assert re.search(r"^\s+quota:\s*\S+", cache_block, re.M), (
        "buildstream-ci.conf declares no cache.quota"
    )


def test_disk_is_logged_around_each_merge():
    """A dead runner leaves no job log. The free-space trail is the only
    evidence the next incident will have."""
    assert BUILD_FINAL.count("df -h /") >= 3, (
        "log free space around the CAS merge and the export"
    )


STALENESS = (REPO / ".github/workflows/staleness-check.yml").read_text()


def test_staleness_check_queries_the_real_build_workflow_name():
    """The check greps `gh run list --workflow "<name>"`. If that string stops
    matching the build workflow's `name:` — a rename, a typo, a copy from a
    sibling repo — the query returns nothing, the check reads that as "no
    successful run", and it opens a stale-build issue every single day while
    the pipeline is perfectly healthy. Both halves must name the same
    workflow."""
    build_name = re.search(r"^name:\s*(.+)$", MULTIRUNNER, re.M).group(1).strip()
    assert f'--workflow "{build_name}"' in STALENESS, (
        f"staleness-check.yml does not query the build workflow's real name "
        f"({build_name!r})"
    )
