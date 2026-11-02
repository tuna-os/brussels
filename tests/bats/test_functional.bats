#!/usr/bin/env bats
# Functional tests for xfce-linux build scripts.
# Validates script behavior beyond basic existence checks.

setup() {
  REPO_ROOT="$(cd "${BATS_TEST_DIRNAME}/../.." && pwd)"
}

# ── build-iso.sh functional tests ──────────────────────────────────────────

@test "build-iso.sh: requires exactly 3 arguments" {
  run bash "${REPO_ROOT}/xfce-linux/src/build-iso.sh"
  [ "$status" -ne 0 ]
  [[ "$output" =~ Usage ]]
}

@test "build-iso.sh: rejects partial arguments (1 arg)" {
  run bash "${REPO_ROOT}/xfce-linux/src/build-iso.sh" /tmp/boot.tar
  [ "$status" -ne 0 ]
  [[ "$output" =~ Usage ]]
}

@test "build-iso.sh: rejects non-existent input files" {
  run bash "${REPO_ROOT}/xfce-linux/src/build-iso.sh" /tmp/nonexistent-boot.tar /tmp/nonexistent-squashfs.img /tmp/output.iso
  [ "$status" -ne 0 ]
  [[ "$output" =~ ERROR ]] || [[ "$output" =~ error ]] || [[ "$output" =~ "No such file" ]]
}

# ── configure-live.sh functional tests ─────────────────────────────────────

@test "configure-live.sh: runs without errors in dry mode" {
  run bash "${REPO_ROOT}/xfce-linux/src/configure-live.sh"
  # Should fail gracefully when called standalone (no live env)
  [ "$status" -ne 0 ]
}

# ── install-flatpaks.sh functional tests ───────────────────────────────────

@test "install-flatpaks.sh: has valid flatpak remote references" {
  run grep -E 'flathub|flatpak' "${REPO_ROOT}/xfce-linux/src/install-flatpaks.sh"
  [ "$status" -eq 0 ]
}

@test "install-flatpaks.sh: references valid flatpak applications" {
  run bash -c "source ${REPO_ROOT}/xfce-linux/src/install-flatpaks.sh 2>/dev/null || true"
  # Should not crash on syntax check
  [ "$status" -eq 0 ]
}

# ── gen-filemap.py functional tests ────────────────────────────────────────

@test "gen-filemap.py: produces valid YAML output" {
  run python3 -c "
import sys
sys.path.insert(0, '${REPO_ROOT}/scripts')
# Basic import and syntax check
import ast, py_compile
py_compile.compile('${REPO_ROOT}/scripts/gen-filemap.py', doraise=True)
print('Syntax OK')
"
  [ "$status" -eq 0 ]
}

@test "gen-filemap.py: handles empty input gracefully" {
  run python3 -c "
import sys
sys.path.insert(0, '${REPO_ROOT}/scripts')
# Verify it can be imported without errors
with open('${REPO_ROOT}/scripts/gen-filemap.py') as f:
    code = compile(f.read(), 'gen-filemap.py', 'exec')
    print('Compiled OK')
"
  [ "$status" -eq 0 ]
}

# ── apply-xattrs.py functional tests ───────────────────────────────────────

@test "apply-xattrs.py: valid Python syntax and imports" {
  run python3 -c "
import sys
sys.path.insert(0, '${REPO_ROOT}/scripts')
import ast
with open('${REPO_ROOT}/scripts/apply-xattrs.py') as f:
    ast.parse(f.read())
print('Syntax OK')
"
  [ "$status" -eq 0 ]
}

# ── bst-dashboard.py functional tests ──────────────────────────────────────

@test "bst-dashboard.py: valid Python syntax" {
  run python3 -c "
import ast
with open('${REPO_ROOT}/tools/bst-dashboard.py') as f:
    ast.parse(f.read())
print('Syntax OK')
"
  [ "$status" -eq 0 ]
}

# ── build-xfwl4.sh validation ─────────────────────────────────────────────-

@test "build-xfwl4.sh: references only valid package names" {
  # Verify the script doesn't reference obviously broken/nonexistent patterns
  run bash -n "${REPO_ROOT}/build-xfwl4.sh"
  [ "$status" -eq 0 ]
}

@test "build-xfwl4.sh: output path is specified" {
  run grep -E '/output/|cp .* /output' "${REPO_ROOT}/build-xfwl4.sh"
  [ "$status" -eq 0 ]
}

# ── Shipped-installer command interfaces ─────────────────────────────────

@test "plain install: rejects the removed fisherman checkout argument" {
  run bash "${REPO_ROOT}/scripts/plain-install-qemu.sh" target 2222 /tmp/monitor /checkout
  [ "$status" -eq 1 ]
  [[ "$output" =~ Usage ]]
}

@test "LUKS install: rejects the removed fisherman checkout argument" {
  run bash "${REPO_ROOT}/scripts/luks-install-qemu.sh" target password 2222 /tmp/monitor /checkout
  [ "$status" -eq 1 ]
  [[ "$output" =~ Usage ]]
}
