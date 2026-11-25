"""brussels-winblues: a layer over the base image, with no trademarked assets."""

from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
CHICAGO95 = REPO / "elements" / "winblues" / "chicago95.bst"


def test_variant_layer_has_no_runtime_dependencies():
    """The compose must hold only the variant's own files, not the base image."""
    layer = yaml.safe_load((REPO / "elements" / "oci" / "layers" / "brussels-winblues.bst").read_text())
    assert layer["kind"] == "compose"
    for name in layer["build-depends"]:
        element = yaml.safe_load((REPO / "elements" / name).read_text())
        assert not element.get("depends"), f"{name} would pull its runtime dependencies into the layer"


def test_chicago95_skips_microsoft_derived_assets():
    script = yaml.safe_load(CHICAGO95.read_text())["config"]["install-commands"][0]
    for unwanted in ("sounds/", "Plymouth", "Extras/Backgrounds", "Fonts/", "Microsoft Windows 95 Startup Sound"):
        assert unwanted not in script, unwanted
    for removed in ("misc", "branding_W95.png", "start-here*", "chromium-browser*", "application-msword*"):
        assert removed in script, removed
    # The audit that fails the build when a removed image survives.
    assert "trademarked artwork still installed" in script


def test_variant_is_built_and_published():
    workflow = (REPO / ".github" / "workflows" / "build-multirunner.yml").read_text()
    assert "VARIANTS: winblues" in workflow
    assert 'just export-variant "$v"' in workflow
    assert "brussels-${v}" in workflow
    containerfile = (REPO / "variants" / "winblues" / "Containerfile").read_text()
    assert "FROM ${BASE_IMAGE}" in containerfile
    assert "VARIANT_ID=winblues" in containerfile


def test_variant_config_is_declared_in_policy():
    policy = yaml.safe_load((REPO / "tests" / "xfce-policy.yml").read_text())
    shipped = sorted(p.relative_to(REPO).as_posix() for p in (REPO / "files" / "winblues").rglob("*.xml"))
    assert shipped
    for path in shipped:
        assert path in policy["config_overrides"], path


def test_chicago95_license_is_in_the_image():
    """GPL-3.0 section 4: recipients get the license text and the notices."""
    licenses = REPO / "files/winblues/usr/share/licenses/chicago95"
    assert "Version 3, 29 June 2007" in (licenses / "GPL-3.0.txt").read_text()
    assert "Larry Ewing" in (licenses / "NOTICE").read_text()
    script = yaml.safe_load(CHICAGO95.read_text())["config"]["install-commands"][0]
    assert "licenses/chicago95/CREDITS" in script
