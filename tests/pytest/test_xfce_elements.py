"""Unit tests and invariants for XFCE elements built from upstream release tags.

Validates that:
- All XFCE desktop components have dedicated .bst elements in elements/xfce-linux/
- The obsolete prebuilt binary tarball element (xfce-binaries.bst) is retired
- The /var/home/james symlink hack is removed from the stack integration commands
- The xfce-wayland-src symlink is removed from repository root
- All XFCE elements have valid YAML structure, kinds, and sources
- include/aliases.yml contains the xfce alias
- xfwl4 installs the upstream session desktop file
"""

import os
from pathlib import Path
from urllib.parse import urlparse
import yaml

REPO = Path(__file__).resolve().parents[2]
ELEMENTS_DIR = REPO / "elements" / "xfce-linux"

EXPECTED_XFCE_ELEMENTS = [
    "xfce4-dev-tools.bst",
    "libxfce4util.bst",
    "xfconf.bst",
    "libxfce4ui.bst",
    "garcon.bst",
    "libxfce4windowing.bst",
    "exo.bst",
    "xfwm4.bst",
    "xfce4-panel.bst",
    "xfce4-session.bst",
    "xfce4-settings.bst",
    "xfdesktop.bst",
    "thunar.bst",
    "tumbler.bst",
    "xfce4-appfinder.bst",
    "xfce4-terminal.bst",
    "xfce4-notifyd.bst",
    "xfce4-power-manager.bst",
    "xfwl4.bst",
]


def test_xfce_binaries_element_retired():
    """xfce-binaries.bst must be deleted (issue #158)."""
    assert not (ELEMENTS_DIR / "xfce-binaries.bst").exists(), (
        "xfce-binaries.bst should be retired and deleted"
    )


def test_xfce_wayland_symlink_retired():
    """xfce-wayland-src symlink must be removed from repo root."""
    assert not (REPO / "xfce-wayland-src").exists(), (
        "xfce-wayland-src symlink should be removed from repository root"
    )


def test_all_expected_xfce_elements_exist():
    """Every component must have a corresponding .bst element."""
    for elem_name in EXPECTED_XFCE_ELEMENTS:
        elem_path = ELEMENTS_DIR / elem_name
        assert elem_path.exists(), f"Missing element: {elem_name}"


TARBALL_ELEMENTS = {"xfce4-dev-tools.bst", "exo.bst", "xfwm4.bst"}


def test_all_xfce_elements_valid_yaml_and_sources():
    """Each element must parse as valid YAML with kind, description, and pinned upstream sources."""
    for elem_name in EXPECTED_XFCE_ELEMENTS:
        elem_path = ELEMENTS_DIR / elem_name
        data = yaml.safe_load(elem_path.read_text())
        assert isinstance(data, dict), f"{elem_name} is not a valid YAML mapping"
        assert "kind" in data, f"{elem_name} missing 'kind'"
        assert "sources" in data, f"{elem_name} missing 'sources'"
        assert len(data["sources"]) >= 1, f"{elem_name} has empty 'sources'"
        first_src = data["sources"][0]
        assert "ref" in first_src, f"{elem_name} missing 'ref'"
        if elem_name in TARBALL_ELEMENTS:
            # Built from the release tarball, which carries generated files
            # the git tag lacks (see the element's comment).
            assert first_src.get("kind") == "tar", f"{elem_name} should use its release tarball"
            assert first_src["url"].startswith("xfce_archive:"), f"{elem_name} tarball must come from archive.xfce.org"
            continue
        assert first_src.get("kind") in ["git_repo", "git_module"], (
            f"{elem_name} first source is not git_repo or git_module"
        )
        assert "track" in first_src, f"{elem_name} missing 'track'"


def test_xfce_alias_in_aliases_yml():
    """include/aliases.yml must define the xfce git alias."""
    aliases_file = REPO / "include" / "aliases.yml"
    data = yaml.safe_load(aliases_file.read_text())
    assert "aliases" in data
    assert "xfce" in data["aliases"], "xfce alias missing from include/aliases.yml"
    assert urlparse(data["aliases"]["xfce"]).hostname == "gitlab.xfce.org"


def test_no_james_symlink_hack_in_stack():
    """xfce-linux-stack.bst must not contain the /var/home/james symlink hack."""
    stack_path = REPO / "elements" / "oci" / "layers" / "xfce-linux-stack.bst"
    content = stack_path.read_text()
    assert "/var/home/james/dev/xfce-wayland" not in content, (
        "xfce-linux-stack.bst still contains /var/home/james symlink hack"
    )


def test_xfce_cluster_references_all_components():
    """xfce-linux-cluster.bst must depend on all built XFCE components and not xfce-binaries."""
    cluster_path = ELEMENTS_DIR / "xfce-linux-cluster.bst"
    content = cluster_path.read_text()
    assert "xfce-binaries.bst" not in content, "xfce-linux-cluster.bst must not reference xfce-binaries.bst"
    for elem_name in EXPECTED_XFCE_ELEMENTS:
        if elem_name == "xfce4-dev-tools.bst":
            continue  # build-time dependency only
        assert f"xfce-linux/{elem_name}" in content, (
            f"xfce-linux-cluster.bst missing dependency on xfce-linux/{elem_name}"
        )


def test_xfwl4_installs_session_desktop():
    """xfwl4.bst must install xfwl4.desktop and session symlink."""
    xfwl4_path = ELEMENTS_DIR / "xfwl4.bst"
    content = xfwl4_path.read_text()
    assert "xfwl4.desktop" in content
    assert "wayland-sessions" in content


def test_no_prebuilt_library_path_workarounds():
    """The ld.so.conf / lib64 links existed only for the prebuilt tree (#294)."""
    assert not (ELEMENTS_DIR / "lib-fixes.bst").exists()
    assert not (REPO / "files" / "lib64-links").exists()
    for conf in REPO.glob("files/**/ld.so.conf.d/xfce-lib.conf"):
        raise AssertionError(f"{conf} only served the prebuilt binaries")
    stack = (REPO / "elements" / "oci" / "layers" / "xfce-linux-stack.bst").read_text()
    assert "/usr/lib64/xfce4" not in stack


def test_session_is_upstream_xfwl4_entry():
    """xfwl4.desktop is the session; the labwc-based xfce-wayland entry is not shipped."""
    xfwl4 = (ELEMENTS_DIR / "xfwl4.bst").read_text()
    assert "resources/xfwl4.desktop.in" in xfwl4
    assert "xfce-wayland.desktop" not in xfwl4
    session = (ELEMENTS_DIR / "xfce4-session.bst").read_text()
    assert 'rm -f "%{install-root}%{datadir}/wayland-sessions/xfce-wayland.desktop"' in session
    stack = REPO / "elements" / "oci" / "layers" / "xfce-linux-stack.bst"
    text = stack.read_text()
    assert "DefaultSession=xfwl4" in text, stack
    assert "Session=xfce-wayland" not in text, stack
    # The live ISO is built from the last published image, which can still
    # carry the old name. configure-live.sh prefers xfwl4 and takes
    # xfce-wayland only when the image has no xfwl4 session
    # (test_live_session_name_comes_from_the_payload_image).
    live = (REPO / "xfce-linux" / "src" / "configure-live.sh").read_text()
    assert "for candidate in xfwl4 xfce-wayland; do" in live
    assert "Session=xfce-wayland" not in live


def test_no_forced_software_rendering():
    """LIBGL_ALWAYS_SOFTWARE came from the prebuilt startxfce4-wayland wrapper."""
    for path in list((REPO / "elements").rglob("*.bst")) + list((REPO / "files").rglob("*")):
        if path.is_file():
            assert "LIBGL_ALWAYS_SOFTWARE" not in path.read_text(errors="ignore"), path


LAYER_SHELL_USERS = {
    "xfce4-panel.bst": "-Dgtk-layer-shell=enabled",
    "xfce4-session.bst": "-Dgtk-layer-shell=enabled",
    "xfce4-settings.bst": "-Dgtk-layer-shell=enabled",
    "xfce4-terminal.bst": "-Dgtk-layer-shell=enabled",
    "xfdesktop.bst": "-Dwayland=enabled",
    "xfce4-notifyd.bst": "-Dwayland=enabled",
}


def test_wayland_components_build_with_gtk_layer_shell():
    """Wayland support is 'auto' upstream; it must be forced on, with gtk-layer-shell."""
    assert (ELEMENTS_DIR / "gtk-layer-shell.bst").exists()
    for name, flag in LAYER_SHELL_USERS.items():
        data = yaml.safe_load((ELEMENTS_DIR / name).read_text())
        assert "xfce-linux/gtk-layer-shell.bst" in data["depends"], name
        assert flag in data["variables"]["meson-local"], name


def test_xfwm4_ships_themes_not_the_x11_wm():
    """xfwm4 is built for its themes and settings dialogs only."""
    content = (ELEMENTS_DIR / "xfwm4.bst").read_text()
    assert 'rm -f "%{install-root}%{bindir}/xfwm4"' in content


def test_screen_locker_is_wayland_xfce4_screensaver():
    """The locker is upstream xfce4-screensaver with its Wayland back end only."""
    data = yaml.safe_load((ELEMENTS_DIR / "xfce4-screensaver.bst").read_text())
    flags = data["variables"]["meson-local"].split()
    assert "-Dwayland=enabled" in flags
    assert "-Dx11=disabled" in flags
    assert "xfce-linux/libwlembed.bst" in data["depends"]
    cluster = (ELEMENTS_DIR / "xfce-linux-cluster.bst").read_text()
    assert "xfce-linux/xfce4-screensaver.bst" in cluster


def test_dbus_glib_installs_into_the_project_libdir():
    """A bare `./configure --prefix=/usr` puts dbus-glib-1.pc in /usr/lib/pkgconfig.

    pkg-config in the SDK reads %{libdir}, so xfce4-screensaver stopped with
    `Dependency "dbus-glib-1" not found` in every chunk that built it (run
    45344668715). The element must keep the project's configure arguments.
    """
    element = yaml.safe_load((ELEMENTS_DIR / "dbus-glib.bst").read_text())
    assert "configure-commands" not in element.get("config", {})
    assert "--disable-static" in element["variables"]["conf-local"]
