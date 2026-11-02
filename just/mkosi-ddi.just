# Local Mkosi raw-GPT DDI. This is separate from the bootc install-to-disk path.
[group('build')]
mkosi-ddi:
    #!/usr/bin/env bash
    set -euo pipefail
    just bst build mkosi/xfce-linux-ddi.bst
    just bst artifact checkout --force mkosi/xfce-linux-ddi.bst --directory /src/.mkosi-root
    kernel=$(find .mkosi-root/usr/lib/modules -mindepth 1 -maxdepth 1 -type d -printf '%f\n' | sort -V | tail -1)
    # Reuse the matching GNOME OS initramfs, not a host/custom-distro initrd.
    initrd=$(realpath ".mkosi-root/usr/lib/modules/${kernel}/initramfs.img")
    test -s "$initrd"
    sudo mkosi --directory=mkosi/ddi --initrd="$initrd" build

[group('build')]
mkosi-ddi-clean:
    sudo mkosi --directory=mkosi/ddi clean
    sudo rm -rf .mkosi-root
