"""Exercise registry-digest capture and fail-closed release prerequisites."""

import os
import json
import textwrap
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]


def tool_env(tmp_path, name, body):
    tool = tmp_path / name
    tool.write_text("#!/usr/bin/env bash\nset -euo pipefail\n" + body)
    tool.chmod(0o755)
    return {**os.environ, "PATH": f"{tmp_path}:{os.environ['PATH']}"}


def run_script(name, *args, env):
    return subprocess.run(
        ["bash", str(REPO / "scripts" / name), *args],
        env=env, text=True, capture_output=True, check=False,
    )


def test_push_returns_destination_digest(tmp_path):
    digest = "sha256:" + "a" * 64
    env = tool_env(tmp_path, "podman", f'''test "$1" = push
 test "$2" = --digestfile
 test "$4" = localhost/fixture:latest
 test "$5" = docker://registry.example/fixture:revision
 printf '%s\\n' '{digest}' > "$3"
''')
    result = run_script(
        "push-image.sh", "localhost/fixture:latest",
        "registry.example/fixture:revision", env=env,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == digest


def test_push_failure_does_not_emit_digest(tmp_path):
    env = tool_env(tmp_path, "podman", "exit 23\n")
    result = run_script("push-image.sh", "local", "registry/image:tag", env=env)
    assert result.returncode == 23
    assert not result.stdout


def test_push_rejects_missing_destination():
    result = run_script("push-image.sh", "local", env=os.environ.copy())
    assert result.returncode == 2
    assert "Usage:" in result.stderr


def test_release_requires_private_secret(tmp_path):
    env = {**os.environ, "COSIGN_PRIVATE_KEY": ""}
    result = run_script("check-release-signing.sh", str(tmp_path / "key"), env=env)
    assert result.returncode == 1
    assert "SIGNING_SECRET" in result.stderr


def test_release_requires_public_key(tmp_path):
    env = {**os.environ, "COSIGN_PRIVATE_KEY": "unit-test-not-a-key"}
    result = run_script("check-release-signing.sh", str(tmp_path / "key"), env=env)
    assert result.returncode == 1
    assert "approved matching public key" in result.stderr


@pytest.mark.parametrize("derived,expected_status", [("approved", 0), ("other", 1)])
def test_release_checks_matching_derived_public_key(tmp_path, derived, expected_status):
    public_key = tmp_path / "cosign.pub"
    public_key.write_text("approved\n")
    env = tool_env(tmp_path, "cosign", f'''test "$1" = public-key
 test "$2" = --key
 test "$3" = env://COSIGN_PRIVATE_KEY
 printf '%s\\n' '{derived}'
''')
    env["COSIGN_PRIVATE_KEY"] = "unit-test-not-a-key"
    result = run_script("check-release-signing.sh", str(public_key), env=env)
    assert result.returncode == expected_status, result.stderr
    if expected_status:
        assert "does not match" in result.stderr


def test_release_propagates_key_decryption_failure(tmp_path):
    public_key = tmp_path / "cosign.pub"
    public_key.write_text("approved\n")
    env = tool_env(tmp_path, "cosign", "exit 19\n")
    env["COSIGN_PRIVATE_KEY"] = "unit-test-not-a-key"
    result = run_script("check-release-signing.sh", str(public_key), env=env)
    assert result.returncode == 19


@pytest.mark.parametrize(
    "different_workflow,pending",
    [(None, False), ("Plain*", False), ("LUKS*", False), (None, True)],
)
def test_promotion_requires_all_health_runs_at_one_completed_commit(
    tmp_path, different_workflow, pending,
):
    workflow = (REPO / ".github/workflows/promote-stable.yml").read_text()
    step = workflow.split(
        "      - name: Health check — latest nightly build + matching ISO green on main\n", 1,
    )[1].split("\n      - name:", 1)[0]
    command = textwrap.dedent(step.split("        run: |\n", 1)[1])
    env = tool_env(tmp_path, "gh", '''case "$4" in
  "Build xfce-linux (Multi-Runner)") printf '%s\\n' "$BUILD_RUN" ;;
  "Build and Publish xfce-linux Live ISO") printf '%s\\n' "$ISO_RUN" ;;
  Plain*) printf '%s\\n' "$PLAIN_RUN" ;;
  LUKS*) printf '%s\\n' "$LUKS_RUN" ;;
  *) exit 3 ;;
esac
''')
    sha = "a" * 40
    record = {"headSha": sha, "status": "completed", "conclusion": "success", "databaseId": 123}
    for name in ("BUILD_RUN", "ISO_RUN", "PLAIN_RUN", "LUKS_RUN"):
        env[name] = json.dumps(record)
    if different_workflow:
        key = "PLAIN_RUN" if different_workflow == "Plain*" else "LUKS_RUN"
        env[key] = json.dumps({**record, "headSha": "b" * 40})
    if pending:
        env["BUILD_RUN"] = json.dumps({**record, "status": "in_progress", "conclusion": None})
    output = tmp_path / "outputs"
    env["GITHUB_OUTPUT"] = str(output)
    result = subprocess.run(
        ["bash", "-e", "-o", "pipefail", "-c", command],
        env=env, capture_output=True, text=True, check=False,
    )
    if different_workflow or pending:
        assert result.returncode == 1, result.stderr
        assert not output.exists() or "sha=" not in output.read_text()
    else:
        assert result.returncode == 0, result.stderr
        assert output.read_text() == f"iso_run=123\nplain_run=123\nluks_run=123\nsha={sha}\n"


def test_iso_verifier_hashes_actual_artifact_and_preserves_trust_checks(tmp_path):
    iso = tmp_path / "fixture.iso"
    iso.write_bytes(b"actual artifact contents")
    import hashlib
    digest = hashlib.sha256(iso.read_bytes()).hexdigest()
    env = tool_env(tmp_path, "cosign", f'''test "$1" = verify-blob
 test "$2" = --bundle
 test "$3" = fixture.sigstore.json
 test "$4" = --certificate-identity
 test "$5" = https://github.com/tuna-os/xfce-linux/workflow
 test "$6" = --certificate-oidc-issuer
 test "$7" = https://token.actions.githubusercontent.com
 test "$8" = sha256:{digest}
 test "$#" = 8
''')
    result = run_script(
        "verify-iso-signature.sh", str(iso), "fixture.sigstore.json",
        "https://github.com/tuna-os/xfce-linux/workflow", env=env,
    )
    assert result.returncode == 0, result.stderr


def test_iso_verifier_refuses_unreadable_artifact_before_cosign(tmp_path):
    env = tool_env(tmp_path, "cosign", "echo should-not-run\\n")
    result = run_script(
        "verify-iso-signature.sh", str(tmp_path / "absent.iso"), "bundle", "identity", env=env,
    )
    assert result.returncode != 0
    assert not result.stdout


def test_iso_verifier_propagates_signature_failure(tmp_path):
    iso = tmp_path / "fixture.iso"
    iso.write_bytes(b"actual artifact contents")
    env = tool_env(tmp_path, "cosign", "exit 31\n")
    result = run_script("verify-iso-signature.sh", str(iso), "bundle", "identity", env=env)
    assert result.returncode == 31


@pytest.mark.parametrize("mismatch", [None, "source_commit", "payload_revision", "payload_image"])
def test_qualification_requires_exact_source_revision_and_digest(tmp_path, mismatch):
    sha = "a" * 40
    image = "registry.example/image@sha256:" + "b" * 64
    record = {"source_commit": sha, "payload_revision": sha, "payload_image": image}
    if mismatch:
        record[mismatch] = "not-the-qualified-candidate"
    evidence = tmp_path / "evidence.json"
    evidence.write_text(json.dumps(record))
    env = tool_env(tmp_path, "gh", '''if [ "$1" = api ]; then
  case "$2" in
    */11) workflow=build-iso.yml ;;
    */12) workflow=test-plain-install.yml ;;
    */13) workflow=test-luks-install.yml ;;
    *) exit 4 ;;
  esac
  printf '{"head_sha":"%s","path":".github/workflows/%s","status":"completed","conclusion":"success"}\\n' "$SHA" "$workflow"
else
  test "$1" = run && test "$2" = download
  mkdir -p "$7"
  cp "$EVIDENCE" "$7/qualification.json"
fi
''')
    env.update(SHA=sha, EVIDENCE=str(evidence))
    result = run_script("verify-qualified-payload.sh", sha, image, "11", "12", "13", env=env)
    assert result.returncode == (1 if mismatch else 0), result.stderr


def test_payload_pinning_records_the_actual_registry_revision(tmp_path):
    sha = "a" * 40
    digest = "sha256:" + "b" * 64
    payload = tmp_path / "payload_ref"
    payload.write_text("registry.example/image:moving\n")
    evidence = tmp_path / "qualification.json"
    image = {"Name": "registry.example/image", "Digest": digest,
             "Labels": {"org.opencontainers.image.revision": sha}}
    env = tool_env(tmp_path, "skopeo", "printf '%s\\n' \"$IMAGE_JSON\"\n")
    env["IMAGE_JSON"] = json.dumps(image)
    result = run_script("pin-qualified-payload.sh", str(payload), str(evidence), sha, env=env)
    assert result.returncode == 0, result.stderr
    assert payload.read_text() == "registry.example/image:moving\n"
    assert json.loads(evidence.read_text()) == {
        "source_commit": sha, "payload_revision": sha,
        "payload_image": f"registry.example/image@{digest}",
    }
