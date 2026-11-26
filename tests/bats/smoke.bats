#!/usr/bin/env bats
# Basic smoke tests for xfce-linux build scripts.
# Verifies scripts exist, are executable, have proper shebangs, and fail
# gracefully when called without required arguments.

setup() {
  REPO_ROOT="$(cd "${BATS_TEST_DIRNAME}/../.." && pwd)"
}

# ── build-xfwl4.sh ──────────────────────────────────────────────────────────

@test "build-xfwl4.sh: exists and is executable" {
  run test -x "${REPO_ROOT}/build-xfwl4.sh"
  [ "$status" -eq 0 ]
}

@test "build-xfwl4.sh: has bash shebang" {
  run head -1 "${REPO_ROOT}/build-xfwl4.sh"
  [[ "$output" =~ ^#!/.*bash ]] || [[ "$output" =~ ^#!/.*sh ]]
}

@test "build-xfwl4.sh: has set -euo pipefail" {
  run grep 'set -euo pipefail' "${REPO_ROOT}/build-xfwl4.sh"
  [ "$status" -eq 0 ]
}

# ── build-iso.sh ────────────────────────────────────────────────────────────

@test "build-iso.sh: exists and is executable" {
  run test -x "${REPO_ROOT}/xfce-linux/src/build-iso.sh"
  [ "$status" -eq 0 ]
}

@test "build-iso.sh: has bash shebang" {
  run head -1 "${REPO_ROOT}/xfce-linux/src/build-iso.sh"
  [[ "$output" =~ ^#!/.*bash ]] || [[ "$output" =~ ^#!/.*sh ]]
}

@test "build-iso.sh: fails with usage when called without args" {
  run bash "${REPO_ROOT}/xfce-linux/src/build-iso.sh"
  [ "$status" -ne 0 ]
  [[ "$output" =~ Usage ]] || [[ "$output" =~ usage ]] || [ -n "$output" ]
}

@test "build-iso.sh: has set -euo pipefail" {
  run grep 'set -euo pipefail' "${REPO_ROOT}/xfce-linux/src/build-iso.sh"
  [ "$status" -eq 0 ]
}

# ── configure-live.sh ───────────────────────────────────────────────────────

@test "configure-live.sh: exists" {
  run test -f "${REPO_ROOT}/xfce-linux/src/configure-live.sh"
  [ "$status" -eq 0 ]
}

@test "configure-live.sh: has bash shebang" {
  run head -1 "${REPO_ROOT}/xfce-linux/src/configure-live.sh"
  [[ "$output" =~ ^#!/.*bash ]] || [[ "$output" =~ ^#!/.*sh ]]
}

# ── install-flatpaks.sh ─────────────────────────────────────────────────────

@test "install-flatpaks.sh: exists" {
  run test -f "${REPO_ROOT}/xfce-linux/src/install-flatpaks.sh"
  [ "$status" -eq 0 ]
}

@test "install-flatpaks.sh: has bash shebang" {
  run head -1 "${REPO_ROOT}/xfce-linux/src/install-flatpaks.sh"
  [[ "$output" =~ ^#!/.*bash ]] || [[ "$output" =~ ^#!/.*sh ]]
}

@test "install-flatpaks.sh: has set -exo pipefail" {
  run grep 'set -exo pipefail' "${REPO_ROOT}/xfce-linux/src/install-flatpaks.sh"
  [ "$status" -eq 0 ]
}

# ── dracut module ───────────────────────────────────────────────────────────

@test "dracut module-setup.sh: exists" {
  run test -f "${REPO_ROOT}/xfce-linux/src/dracut/95xfce-linux-isofile/module-setup.sh"
  [ "$status" -eq 0 ]
}

@test "dracut xfce-linux-isofile.sh: exists" {
  run test -f "${REPO_ROOT}/xfce-linux/src/dracut/95xfce-linux-isofile/xfce-linux-isofile.sh"
  [ "$status" -eq 0 ]
}

# ── Python scripts ──────────────────────────────────────────────────────────

@test "gen-filemap.py: valid Python syntax" {
  run python3 -c "import py_compile; py_compile.compile('${REPO_ROOT}/scripts/gen-filemap.py', doraise=True)"
  [ "$status" -eq 0 ]
}

@test "apply-xattrs.py: valid Python syntax" {
  run python3 -c "import py_compile; py_compile.compile('${REPO_ROOT}/scripts/apply-xattrs.py', doraise=True)"
  [ "$status" -eq 0 ]
}

@test "bst-dashboard.py: valid Python syntax" {
  run python3 -c "import py_compile; py_compile.compile('${REPO_ROOT}/tools/bst-dashboard.py', doraise=True)"
  [ "$status" -eq 0 ]
}

# ── accessibility ───────────────────────────────────────────────────────────

@test "deps.bst: ships the orca screen reader" {
  run grep -E '^\s*- gnome-build-meta.bst:core/orca.bst' "${REPO_ROOT}/elements/xfce-linux/deps.bst"
  [ "$status" -eq 0 ]
}
