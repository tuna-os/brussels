"""Static contracts for the local Mkosi DDI and shared OS identity."""

from configparser import ConfigParser
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (REPO / path).read_text()


def test_mkosi_uses_one_buildstream_compose_root():
    config = _read("mkosi/ddi/mkosi.conf")
    target = _read("elements/mkosi/xfce-linux-ddi.bst")
    parsed = ConfigParser(interpolation=None)
    parsed.read_string(config)

    assert parsed["Config"]["MinimumVersion"] == "26"
    assert parsed["Distribution"]["Distribution"] == "custom"
    assert parsed["Content"]["BaseTrees"] == "../../.mkosi-root"
    assert parsed["Output"]["RepartDirectories"] == "mkosi.repart"
    assert parsed["Content"]["Bootable"] == "yes"
    recipe = _read("just/mkosi-ddi.just")
    assert "just bst build mkosi/xfce-linux-ddi.bst" in recipe
    assert "just bst artifact checkout --force mkosi/xfce-linux-ddi.bst" in recipe
    assert "kind: compose" in target
    assert "oci/layers/xfce-linux-runtime.bst" in target
    assert "oci/xfce-linux.bst" not in config


def test_ddi_declares_separate_efi_and_root_partitions():
    config = _read("mkosi/ddi/mkosi.conf")
    esp = _read("mkosi/ddi/mkosi.repart/10-esp.conf")
    root = _read("mkosi/ddi/mkosi.repart/20-root.conf")

    assert "Type=esp" in esp and "Format=vfat" in esp
    assert "Type=root-x86-64" in root and "Format=ext4" in root
    assert "MountPoint=/boot" in esp
    assert "MountPoint=/" in root


def test_repository_os_identity_reaches_oci_and_ddi():
    os_release = _read("files/etc/os-release")
    oci = _read("elements/oci/xfce-linux.bst")
    ddi_config = _read("mkosi/ddi/mkosi.conf")
    ddi = _read("elements/mkosi/xfce-linux-ddi.bst")
    payload_ref = _read("xfce-linux/payload_ref").strip()
    stack = _read("elements/oci/layers/xfce-linux-stack.bst")

    assert "ID=xfce-linux" in os_release
    assert "VERSION_CODENAME=brussels" in os_release
    assert 'PRETTY_NAME="Brussels (TunaOS)"' in os_release
    assert "oci/os-release.bst" in oci
    assert "/identity/usr/lib/os-release /layer/usr/lib/os-release" in oci
    assert "ExtraTrees=../../files/etc/os-release:/usr/lib/os-release" in ddi_config
    assert "oci/layers/xfce-linux-runtime.bst" in ddi
    assert "xfce-linux/deps.bst" in stack
    assert "gnome-build-meta.bst:oci/gnomeos/stack.bst" in stack
    assert payload_ref.startswith("ghcr.io/tuna-os/xfce-linux:")


def test_local_ddi_recipe_does_not_replace_bootc_disk_recipe():
    recipe = _read("just/mkosi-ddi.just")
    bootc_recipe = _read("just/disk-image.just")

    assert "mkosi --directory=mkosi/ddi" in recipe
    assert "Format=disk" in _read("mkosi/ddi/mkosi.conf")
    assert "bootc install to-disk" in bootc_recipe
    assert "push" not in recipe
