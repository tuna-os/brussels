"""XFCE policy gate: component set, patch headers, shipped xfconf config.

The checks live in scripts/check-xfce-policy.py so CI and a local run use
the same code. These tests run the offline checks against the tree (the
gate) and against synthetic input (the checks themselves).
"""

import importlib.util
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("xfce_policy", REPO / "scripts" / "check-xfce-policy.py")
policy_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy_mod)


@pytest.fixture(scope="module")
def policy():
    return policy_mod.load_policy()


def test_component_set_is_coherent(policy):
    assert policy_mod.check_components(policy) == []


def test_applied_patches_have_headers(policy):
    assert policy_mod.check_patches(policy) == []


def test_shipped_xfconf_is_declared(policy):
    assert policy_mod.check_config(policy, upstream=False) == []


@pytest.mark.parametrize(
    "src, expected",
    [
        ({"kind": "git_repo", "ref": "thunar-4.21.7-0-g" + "a" * 40}, ("4.21.7", "tag")),
        ({"kind": "git_repo", "ref": "thunar-4.21.7-3-g" + "a" * 40}, (None, "snapshot")),
        ({"kind": "git_repo", "ref": "b" * 40}, (None, "snapshot")),
        ({"kind": "tar", "url": "xfce_archive:src/xfce/exo/4.21/exo-4.21.0.tar.bz2"}, ("4.21.0", "tarball")),
    ],
)
def test_pinned_version(src, expected):
    assert policy_mod.pinned_version(src) == expected


def test_off_series_core_component_fails(monkeypatch):
    src = {"kind": "git_repo", "url": "xfce:xfce/xfce4-panel.git", "ref": "xfce4-panel-4.20.8-0-g" + "c" * 40}
    monkeypatch.setattr(policy_mod, "xfce_elements", lambda: iter([("xfce-linux/xfce4-panel.bst", src, "xfce")]))
    errors = policy_mod.check_components({})
    assert any("not in the 4.21 series" in e for e in errors)


def test_unrecorded_snapshot_fails(monkeypatch):
    src = {"kind": "git_repo", "url": "xfce:kelnos/libwlembed.git", "ref": "d" * 40}
    monkeypatch.setattr(policy_mod, "xfce_elements", lambda: iter([("xfce-linux/libwlembed.bst", src, "kelnos")]))
    assert any("git snapshot" in e for e in policy_mod.check_components({}))


def test_patch_header_parsing():
    good = "Subject: x\nUpstream: https://gitlab.xfce.org/x/-/merge_requests/1\nUpstream-Status: Submitted\nReason: y\n---\n"
    assert policy_mod.patch_header(good) == {
        "Upstream": "https://gitlab.xfce.org/x/-/merge_requests/1",
        "Upstream-Status": "Submitted",
        "Reason": "y",
    }
    assert policy_mod.patch_header("Subject: x\n---\ndiff --git a b\nReason: in the diff\n") == {}


def test_xfconf_flatten():
    xml = """<channel name="xsettings" version="1.0">
      <property name="Net" type="empty">
        <property name="ThemeName" type="string" value="Chicago95"/>
      </property>
      <property name="list" type="array"><value type="int" value="1"/><value type="int" value="2"/></property>
    </channel>"""
    assert policy_mod.flatten_xml(xml) == {"/Net/ThemeName": "Chicago95", "/list": "1;2"}
    assert policy_mod.flatten_keyvalue("theme=Default\n# c\nbutton_layout=O|SHMC\n") == {
        "/general/theme": "Default",
        "/general/button_layout": "O|SHMC",
    }


def test_config_drift_against_upstream(monkeypatch, tmp_path):
    """--upstream: an undeclared difference is drift, a declared no-op is dead."""
    chan = tmp_path / "files" / "x" / "xfce-perchannel-xml" / "xsettings.xml"
    chan.parent.mkdir(parents=True)
    chan.write_text(
        '<channel name="xsettings" version="1.0"><property name="Net" type="empty">'
        '<property name="ThemeName" type="string" value="Chicago95"/>'
        '<property name="IconThemeName" type="string" value="Adwaita"/>'
        '<property name="CursorBlink" type="bool" value="false"/>'
        "</property></channel>"
    )
    upstream = (
        '<channel name="xsettings" version="1.0"><property name="Net" type="empty">'
        '<property name="ThemeName" type="string" value="Adwaita"/>'
        '<property name="IconThemeName" type="string" value="Adwaita"/>'
        '<property name="CursorBlink" type="bool" value="true"/>'
        "</property></channel>"
    )
    monkeypatch.setattr(policy_mod, "REPO", tmp_path)
    monkeypatch.setattr(policy_mod, "channel_files", lambda: [chan])
    monkeypatch.setattr(policy_mod, "fetch_upstream", lambda component, file: upstream)
    rel = "files/x/xfce-perchannel-xml/xsettings.xml"
    policy = {"config_overrides": {rel: {"reason": "r", "properties": ["/Net/ThemeName", "/Net/IconThemeName"]}}}
    errors = policy_mod.check_config(policy, upstream=True)
    assert any("/Net/CursorBlink" in e and "drift" in e for e in errors), errors
    assert any("/Net/IconThemeName" in e and "upstream default" in e for e in errors), errors
    assert not any("/Net/ThemeName" in e for e in errors), errors
