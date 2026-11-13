"""Unit tests for scripts/ghcr-blob-stream.py.

The script restores multi-GB CAS blobs from GHCR and must survive mid-stream
cuts by resuming with HTTP Range, then verify the sha256 of the whole stream.
These tests replace the network with a scripted fake `urlopen`.
"""

import base64
import hashlib
import http.client
import importlib.util
import io
import json
import sys
import urllib.error
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
MODULE_PATH = PROJECT_ROOT / "scripts" / "ghcr-blob-stream.py"
spec = importlib.util.spec_from_file_location("ghcr_blob_stream", MODULE_PATH)
ghcr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ghcr)

REF = "ghcr.io/tuna-os/xfce-linux/cache-xfce-linux-core:latest"
REPO = "tuna-os/xfce-linux/cache-xfce-linux-core"
BLOB = b"0123456789" * 10
DIGEST = "sha256:" + hashlib.sha256(BLOB).hexdigest()


class FakeResponse:
    """A urlopen() result: `data` is served, then `cut` (if any) is raised."""

    def __init__(self, data=b"", status=200, cut=None):
        self._buf = io.BytesIO(data)
        self.status = status
        self._cut = cut

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self, n=-1):
        chunk = self._buf.read(n)
        if not chunk and self._cut is not None:
            raise self._cut
        return chunk


class FakeRegistry:
    """Scripted urlopen. Token requests are answered with `token-N`;
    blob requests pop the next scripted behaviour and are recorded."""

    def __init__(self, script):
        self.script = list(script)
        self.blob_requests = []
        self.token_requests = []

    def __call__(self, req, timeout=None):
        if "/token?" in req.full_url:
            self.token_requests.append(req)
            body = json.dumps({"token": f"token-{len(self.token_requests)}"}).encode()
            return FakeResponse(body)
        self.blob_requests.append(req)
        step = self.script.pop(0)
        if isinstance(step, BaseException):
            raise step
        return step


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(ghcr.time, "sleep", lambda _s: None)


@pytest.fixture
def isolated_auth(monkeypatch, tmp_path):
    """Keep the host's real docker/podman credentials out of every test."""
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.delenv("DOCKER_CONFIG", raising=False)
    monkeypatch.delenv("XDG_RUNTIME_DIR", raising=False)


def run_main(monkeypatch, registry, size=len(BLOB), digest=DIGEST, ref=REF):
    monkeypatch.setattr(ghcr.urllib.request, "urlopen", registry)
    monkeypatch.setattr(sys, "argv", ["ghcr-blob-stream.py", ref, digest, str(size)])
    return ghcr.main()


def http_error(code):
    return urllib.error.HTTPError("https://ghcr.io/x", code, "err", {}, None)


class TestUsage:
    def test_wrong_arg_count_prints_usage_and_returns_2(self, monkeypatch, capsys):
        monkeypatch.setattr(sys, "argv", ["ghcr-blob-stream.py", REF])
        assert ghcr.main() == 2
        assert "Usage: ghcr-blob-stream.py" in capsys.readouterr().err


class TestStreaming:
    def test_streams_blob_and_verifies_digest(self, monkeypatch, capsysbinary, isolated_auth):
        registry = FakeRegistry([FakeResponse(BLOB)])
        assert run_main(monkeypatch, registry) == 0
        out = capsysbinary.readouterr()
        assert out.out == BLOB
        assert b"digest verified" in out.err
        assert len(registry.blob_requests) == 1
        assert registry.blob_requests[0].get_header("Range") is None

    def test_blob_url_and_bearer_token(self, monkeypatch, capsysbinary, isolated_auth):
        registry = FakeRegistry([FakeResponse(BLOB)])
        assert run_main(monkeypatch, registry) == 0
        req = registry.blob_requests[0]
        assert req.full_url == f"https://ghcr.io/v2/{REPO}/blobs/{DIGEST}"
        assert req.get_header("Authorization") == "Bearer token-1"

    @pytest.mark.parametrize(
        "ref",
        [
            f"ghcr.io/{REPO}:latest",
            f"ghcr.io/{REPO}",
            f"ghcr.io/{REPO}@sha256:{'a' * 64}",
        ],
    )
    def test_ref_forms_resolve_to_same_repo(self, monkeypatch, capsysbinary, isolated_auth, ref):
        registry = FakeRegistry([FakeResponse(BLOB)])
        assert run_main(monkeypatch, registry, ref=ref) == 0
        assert registry.blob_requests[0].full_url == f"https://ghcr.io/v2/{REPO}/blobs/{DIGEST}"

    def test_empty_blob_makes_no_blob_request(self, monkeypatch, capsysbinary, isolated_auth):
        empty = "sha256:" + hashlib.sha256(b"").hexdigest()
        registry = FakeRegistry([])
        assert run_main(monkeypatch, registry, size=0, digest=empty) == 0
        assert registry.blob_requests == []
        assert capsysbinary.readouterr().out == b""


class TestResume:
    def test_resumes_with_range_after_connection_cut(self, monkeypatch, capsysbinary, isolated_auth):
        registry = FakeRegistry(
            [
                FakeResponse(BLOB[:40], cut=ConnectionResetError("cut")),
                FakeResponse(BLOB[40:], status=206),
            ]
        )
        assert run_main(monkeypatch, registry) == 0
        out = capsysbinary.readouterr()
        # Each byte is written exactly once: no duplication across the resume.
        assert out.out == BLOB
        assert b"connection cut at byte 40/100" in out.err
        assert registry.blob_requests[1].get_header("Range") == "bytes=40-"

    def test_resumes_after_http_exception(self, monkeypatch, capsysbinary, isolated_auth):
        registry = FakeRegistry(
            [
                FakeResponse(BLOB[:10], cut=http.client.IncompleteRead(b"")),
                FakeResponse(BLOB[10:], status=206),
            ]
        )
        assert run_main(monkeypatch, registry) == 0
        assert capsysbinary.readouterr().out == BLOB

    def test_resumes_after_short_read(self, monkeypatch, capsysbinary, isolated_auth):
        # A clean EOF before `size` bytes is a short read, not success.
        registry = FakeRegistry(
            [FakeResponse(BLOB[:60]), FakeResponse(BLOB[60:], status=206)]
        )
        assert run_main(monkeypatch, registry) == 0
        out = capsysbinary.readouterr()
        assert out.out == BLOB
        assert b"short read at byte 60/100" in out.err
        assert registry.blob_requests[1].get_header("Range") == "bytes=60-"

    def test_fails_when_server_ignores_range(self, monkeypatch, capsysbinary, isolated_auth):
        # A 200 on a resumed request would restart from byte 0 and corrupt
        # the stream, so it must be refused.
        registry = FakeRegistry(
            [FakeResponse(BLOB[:40], cut=OSError("cut")), FakeResponse(BLOB, status=200)]
        )
        assert run_main(monkeypatch, registry) == 1
        out = capsysbinary.readouterr()
        assert out.out == BLOB[:40]
        assert b"server ignored Range (HTTP 200)" in out.err


class TestHttpErrors:
    def test_401_refreshes_token_and_retries(self, monkeypatch, capsysbinary, isolated_auth):
        registry = FakeRegistry([http_error(401), FakeResponse(BLOB)])
        assert run_main(monkeypatch, registry) == 0
        assert len(registry.token_requests) == 2
        assert registry.blob_requests[0].get_header("Authorization") == "Bearer token-1"
        assert registry.blob_requests[1].get_header("Authorization") == "Bearer token-2"
        assert b"HTTP 401" in capsysbinary.readouterr().err

    def test_other_http_error_retries_with_same_token(self, monkeypatch, capsysbinary, isolated_auth):
        registry = FakeRegistry([http_error(503), FakeResponse(BLOB)])
        assert run_main(monkeypatch, registry) == 0
        assert len(registry.token_requests) == 1
        assert registry.blob_requests[1].get_header("Authorization") == "Bearer token-1"

    def test_gives_up_after_max_attempts(self, monkeypatch, capsysbinary, isolated_auth):
        registry = FakeRegistry([http_error(503)] * ghcr.MAX_ATTEMPTS)
        assert run_main(monkeypatch, registry) == 1
        out = capsysbinary.readouterr()
        assert out.out == b""
        assert f"giving up after {ghcr.MAX_ATTEMPTS} attempts".encode() in out.err
        assert len(registry.blob_requests) == ghcr.MAX_ATTEMPTS

    def test_backoff_is_capped_at_30_seconds(self, monkeypatch, capsysbinary, isolated_auth):
        sleeps = []
        monkeypatch.setattr(ghcr.time, "sleep", sleeps.append)
        registry = FakeRegistry([http_error(503)] * ghcr.MAX_ATTEMPTS)
        assert run_main(monkeypatch, registry) == 1
        assert sleeps[:3] == [2, 4, 6]
        assert max(sleeps) == 30


class TestIntegrity:
    def test_digest_mismatch_fails(self, monkeypatch, capsysbinary, isolated_auth):
        bad = bytes([BLOB[0] ^ 0xFF]) + BLOB[1:]
        registry = FakeRegistry([FakeResponse(bad)])
        assert run_main(monkeypatch, registry) == 1
        assert b"digest mismatch" in capsysbinary.readouterr().err

    def test_digest_covers_bytes_across_a_resume(self, monkeypatch, capsysbinary, isolated_auth):
        # The hash is accumulated over both attempts, so a corrupted second
        # half is caught even though each attempt on its own looks complete.
        bad_tail = b"X" * (len(BLOB) - 40)
        registry = FakeRegistry(
            [FakeResponse(BLOB[:40], cut=OSError("cut")), FakeResponse(bad_tail, status=206)]
        )
        assert run_main(monkeypatch, registry) == 1
        assert b"digest mismatch" in capsysbinary.readouterr().err

    def test_never_reads_past_declared_size(self, monkeypatch, capsysbinary, isolated_auth):
        registry = FakeRegistry([FakeResponse(BLOB + b"extra-trailing-bytes")])
        assert run_main(monkeypatch, registry) == 0
        assert capsysbinary.readouterr().out == BLOB


class TestAuth:
    def write_config(self, path, registry_key, auth):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"auths": {registry_key: {"auth": auth}}}))

    def test_basic_auth_none_without_any_config(self, isolated_auth):
        assert ghcr.basic_auth("ghcr.io") is None

    def test_basic_auth_from_docker_config_env(self, monkeypatch, tmp_path, isolated_auth):
        self.write_config(tmp_path / "dc" / "config.json", "ghcr.io", "abc")
        monkeypatch.setenv("DOCKER_CONFIG", str(tmp_path / "dc"))
        assert ghcr.basic_auth("ghcr.io") == "abc"

    def test_basic_auth_accepts_https_prefixed_key(self, tmp_path, isolated_auth):
        self.write_config(tmp_path / "home" / ".docker" / "config.json", "https://ghcr.io", "def")
        assert ghcr.basic_auth("ghcr.io") == "def"

    def test_basic_auth_from_containers_auth_json(self, monkeypatch, tmp_path, isolated_auth):
        self.write_config(tmp_path / "xdg" / "containers" / "auth.json", "ghcr.io", "ghi")
        monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path / "xdg"))
        assert ghcr.basic_auth("ghcr.io") == "ghi"

    def test_basic_auth_ignores_other_registries(self, tmp_path, isolated_auth):
        self.write_config(tmp_path / "home" / ".docker" / "config.json", "quay.io", "zzz")
        assert ghcr.basic_auth("ghcr.io") is None

    def test_basic_auth_skips_corrupt_config_and_uses_next(self, monkeypatch, tmp_path, isolated_auth):
        bad = tmp_path / "dc" / "config.json"
        bad.parent.mkdir()
        bad.write_text("{not json")
        monkeypatch.setenv("DOCKER_CONFIG", str(bad.parent))
        self.write_config(tmp_path / "home" / ".docker" / "config.json", "ghcr.io", "next")
        assert ghcr.basic_auth("ghcr.io") == "next"

    def test_bearer_anonymous_when_no_credentials(self, monkeypatch, isolated_auth):
        registry = FakeRegistry([])
        monkeypatch.setattr(ghcr.urllib.request, "urlopen", registry)
        assert ghcr.bearer("ghcr.io", REPO) == "token-1"
        req = registry.token_requests[0]
        assert req.get_header("Authorization") is None
        assert req.full_url == (
            f"https://ghcr.io/token?service=ghcr.io&scope=repository:{REPO}:pull"
        )

    def test_bearer_sends_basic_credentials(self, monkeypatch, tmp_path, isolated_auth):
        auth = base64.b64encode(b"user:pat").decode()
        self.write_config(tmp_path / "home" / ".docker" / "config.json", "ghcr.io", auth)
        registry = FakeRegistry([])
        monkeypatch.setattr(ghcr.urllib.request, "urlopen", registry)
        ghcr.bearer("ghcr.io", REPO)
        assert registry.token_requests[0].get_header("Authorization") == f"Basic {auth}"
