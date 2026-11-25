"""Invariants for the Brussels rename (docs/migration-brussels.md).

Installed systems track ghcr.io/tuna-os/xfce-linux. Each publish path must
keep that name on the same digest as ghcr.io/tuna-os/brussels, and the
BuildStream identifiers must not move: a new project name is a full cold
rebuild.
"""

import os
import stat
import subprocess
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
WORKFLOWS = REPO / ".github" / "workflows"
MULTIRUNNER = (WORKFLOWS / "build-multirunner.yml").read_text()
FALLBACK = (WORKFLOWS / "build-and-publish-xfce-linux.yml").read_text()
SCRIPT = REPO / "scripts" / "publish-alias.sh"


def test_buildstream_identifiers_did_not_move():
    project = yaml.safe_load((REPO / "project.conf").read_text())
    assert project["name"] == "xfce-linux"
    assert (REPO / "elements" / "oci" / "xfce-linux.bst").is_file()
    env = yaml.safe_load(MULTIRUNNER)["env"]
    assert env["IMAGE_NAME"] == "xfce-linux"
    assert env["BST_TARGET"] == "oci/xfce-linux.bst"


def test_publish_name_and_alias():
    for text in (MULTIRUNNER, FALLBACK):
        env = yaml.safe_load(text)["env"]
        assert env["PUBLISH_NAME"] == "brussels"
        assert "xfce-linux" in env["ALIAS_NAMES"].split()
        assert "scripts/publish-alias.sh" in text
        # The primary push never goes to the BuildStream name.
        assert "podman push \"${IMAGE_REGISTRY}/${IMAGE_NAME}" not in text
        assert "podman push \"${IMAGE_REGISTRY}/${{ env.IMAGE_NAME }}" not in text


def test_alias_step_is_a_gate():
    steps = yaml.safe_load(MULTIRUNNER)["jobs"]["build_final"]["steps"]
    alias = next(s for s in steps if s.get("id") == "alias")
    assert not alias.get("continue-on-error")
    assert "|| echo" not in alias["run"]
    assert "|| true" not in alias["run"]
    push = next(s for s in steps if s.get("id") == "push")
    assert alias["if"] == push["if"]
    assert steps.index(alias) > steps.index(push)


def test_each_name_is_signed():
    jobs = yaml.safe_load(MULTIRUNNER)["jobs"]
    job = jobs["sign_final"]
    sign = next(s for s in job["steps"] if s.get("name") == "Sign images (cosign keyless)")
    assert "for name in ${PUBLISH_NAME} ${ALIAS_NAMES}" in sign["run"]
    assert "for ref in ${VARIANT_REFS}" in sign["run"]
    assert "if" not in sign and not sign.get("continue-on-error")
    outputs = jobs["build_final"]["outputs"]
    assert outputs["digest"] == "${{ steps.push.outputs.digest }}"
    assert outputs["variant_refs"] == "${{ steps.push_variants.outputs.refs }}"


def test_the_sign_job_is_keyless_and_runs_no_repository_code():
    job = yaml.safe_load(MULTIRUNNER)["jobs"]["sign_final"]
    assert job["permissions"] == {"packages": "write", "id-token": "write"}
    assert "environment" not in job
    assert not any("checkout" in s.get("uses", "") for s in job["steps"])
    assert "--key" not in str(job)
    assert "SIGNING_SECRET" not in MULTIRUNNER
    verify = job["steps"][-1]["run"].split("cosign verify", 1)[1]
    assert '--certificate-identity "${GITHUB_SERVER_URL}/${GITHUB_WORKFLOW_REF}"' in verify


def test_the_document_gives_the_workflow_identity():
    text = (REPO / "docs" / "signing.md").read_text()
    workflow = "https://github.com/tuna-os/brussels/.github/workflows/build-multirunner.yml"
    for branch in ("main", "stable"):
        assert f"--certificate-identity {workflow}@refs/heads/{branch}" in text


def test_stable_promotion_and_rollback_cover_both_names():
    for name in ("promote-stable.yml", "rollback-stable.yml"):
        text = (WORKFLOWS / name).read_text()
        assert "for name in brussels xfce-linux" in text, name


def test_os_release_identity():
    fields = dict(
        line.split("=", 1)
        for line in (REPO / "files" / "etc" / "os-release").read_text().splitlines()
        if "=" in line
    )
    assert fields["NAME"] == '"Brussels"'
    assert fields["ID"] == "brussels"
    assert fields["ID_LIKE"] == "fedora"
    assert "tuna-os/brussels" in fields["HOME_URL"]


def fake_skopeo(tmp_path, alias_digest):
    """A skopeo that records calls and reports one digest for each name."""
    log = tmp_path / "skopeo.log"
    fake = tmp_path / "skopeo"
    fake.write_text(
        "#!/usr/bin/env bash\n"
        f'echo "$*" >> "{log}"\n'
        'if [ "$1" = inspect ]; then\n'
        '  case "${!#}" in\n'
        f'    *xfce-linux*) echo "{alias_digest}" ;;\n'
        '    *) echo "sha256:aaa" ;;\n'
        "  esac\n"
        "fi\n"
    )
    fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
    return fake, log


def run_alias(fake, *args):
    return subprocess.run(
        ["bash", str(SCRIPT), *args],
        env={**os.environ, "SKOPEO": str(fake)},
        capture_output=True,
        text=True,
        check=False,
    )


def test_alias_script_copies_each_tag_with_preserved_digest(tmp_path):
    fake, log = fake_skopeo(tmp_path, "sha256:aaa")
    result = run_alias(fake, "ghcr.io/tuna-os", "brussels", "xfce-linux", "latest nightly")
    assert result.returncode == 0, result.stderr
    copies = [line for line in log.read_text().splitlines() if line.startswith("copy")]
    assert copies == [
        "copy --all --preserve-digests docker://ghcr.io/tuna-os/brussels:latest docker://ghcr.io/tuna-os/xfce-linux:latest",
        "copy --all --preserve-digests docker://ghcr.io/tuna-os/brussels:nightly docker://ghcr.io/tuna-os/xfce-linux:nightly",
    ]


def test_alias_script_fails_on_digest_mismatch(tmp_path):
    fake, _ = fake_skopeo(tmp_path, "sha256:bbb")
    result = run_alias(fake, "ghcr.io/tuna-os", "brussels", "xfce-linux", "latest")
    assert result.returncode != 0
    assert "alias digest mismatch" in result.stderr


def test_alias_script_rejects_primary_as_alias(tmp_path):
    fake, _ = fake_skopeo(tmp_path, "sha256:aaa")
    result = run_alias(fake, "ghcr.io/tuna-os", "brussels", "brussels", "latest")
    assert result.returncode != 0


def test_publish_digest_comes_from_the_registry():
    """`podman inspect` reports a digest the registry does not have (#308)."""
    steps = yaml.safe_load(MULTIRUNNER)["jobs"]["build_final"]["steps"]
    for step_id in ("push", "push_variants"):
        run = next(s for s in steps if s.get("id") == step_id)["run"]
        assert "--digestfile" in run, step_id
        assert "$(sudo podman inspect" not in run, step_id
        assert "failed three times" in run, step_id
