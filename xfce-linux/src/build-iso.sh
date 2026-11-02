#!/usr/bin/bash
# build-iso.sh <boot-files-tar> <squashfs-img> <output-iso>
#
# Creates a UEFI-bootable systemd-boot live ISO from pre-built components:
#   <boot-files-tar>  — tar containing kernel + EFI files from the rootfs
#   <squashfs-img>    — squashfs of the full live rootfs
#   <output-iso>      — path for the resulting .iso
#
# Identical to the dakota-iso build-iso.sh except for branding labels.

set -euo pipefail

BOOT_TAR="${1:?Usage: build-iso.sh <boot-files-tar> <squashfs-img> <output-iso>}"
SQUASHFS_SRC="${2:?Usage: build-iso.sh <boot-files-tar> <squashfs-img> <output-iso>}"
OUTPUT_ISO="${3:?Usage: build-iso.sh <boot-files-tar> <squashfs-img> <output-iso>}"
LABEL="XFCE_LINUX_LIVE"

WORK=$(mktemp -d "${TMPDIR:-/tmp}/iso-build.XXXXXX")
cleanup() {
  chmod -R u+rwX "${WORK}" 2>/dev/null
  rm -rf "${WORK}"
}
trap cleanup EXIT

BOOT_DIR="${WORK}/boot-files"
ISO_ROOT="${WORK}/iso-root"
ESP_STAGING="${WORK}/esp-staging"

mkdir -p "${BOOT_DIR}" "${ISO_ROOT}/EFI" "${ISO_ROOT}/LiveOS"

echo ">>> Extracting boot files..."
tar -xf "${BOOT_TAR}" -C "${BOOT_DIR}" --no-same-owner

kernel=$(ls "${BOOT_DIR}/usr/lib/modules" | sort -V | tail -1)
echo ">>> Kernel: ${kernel}"

VMLINUZ="${BOOT_DIR}/usr/lib/modules/${kernel}/vmlinuz"
INITRD="${BOOT_DIR}/usr/lib/modules/${kernel}/initramfs.img"

BOOT_EFI_SRC=""
BOOT_EFI_DEST=""
for _candidate in \
    "systemd-bootaa64.efi:EFI/BOOT/BOOTAA64.EFI" \
    "systemd-bootx64.efi:EFI/BOOT/BOOTX64.EFI"; do
    _src="${BOOT_DIR}/usr/lib/systemd/boot/efi/${_candidate%%:*}"
    _dest="${_candidate##*:}"
    if [[ -f "${_src}" ]]; then
        BOOT_EFI_SRC="${_src}"
        BOOT_EFI_DEST="${_dest}"
        break
    fi
done
[[ -n "${BOOT_EFI_SRC}" ]] || { echo "ERROR: no systemd-boot EFI binary found in boot-files tar"; exit 1; }

for f in "${VMLINUZ}" "${INITRD}" "${BOOT_EFI_SRC}"; do
    [[ -f "${f}" ]] || { echo "ERROR: missing ${f}"; exit 1; }
done
echo ">>> Kernel:    $(du -sh "${VMLINUZ}"  | cut -f1)"
echo ">>> Initramfs: $(du -sh "${INITRD}"   | cut -f1)"
echo ">>> EFI:       ${BOOT_EFI_SRC} → ${BOOT_EFI_DEST}"

mkdir -p \
    "${ESP_STAGING}/EFI/BOOT" \
    "${ESP_STAGING}/loader/entries" \
    "${ESP_STAGING}/images/pxeboot"

cp "${BOOT_EFI_SRC}" "${ESP_STAGING}/${BOOT_EFI_DEST}"
cp "${VMLINUZ}" "${ESP_STAGING}/images/pxeboot/vmlinuz"
cp "${INITRD}"  "${ESP_STAGING}/images/pxeboot/initrd.img"

cat > "${ESP_STAGING}/loader/loader.conf" << 'EOF'
timeout 5
default xfce-linux-live.conf
EOF

cat > "${ESP_STAGING}/loader/entries/xfce-linux-live.conf" << EOF
title   Brussels Live (TunaOS)
linux   /images/pxeboot/vmlinuz
initrd  /images/pxeboot/initrd.img
options root=live:CDLABEL=${LABEL} rd.live.image rd.live.overlay.overlayfs=1 enforcing=0 quiet console=ttyS0,115200n8 console=ttyAMA0,115200n8
EOF

INITRD_MB=$(du -m "${INITRD}"  | cut -f1)
VMLINUZ_MB=$(du -m "${VMLINUZ}" | cut -f1)
ESP_MB=$(( INITRD_MB + VMLINUZ_MB + 4 + 32 ))
ESP_IMG="${ISO_ROOT}/EFI/efi.img"

echo ">>> Creating ${ESP_MB} MiB FAT ESP image..."
truncate -s "${ESP_MB}M" "${ESP_IMG}"
mkfs.fat -F 32 -n "ESP" "${ESP_IMG}"

export MTOOLS_SKIP_CHECK=1

mmd -i "${ESP_IMG}" \
    ::/EFI \
    ::/EFI/BOOT \
    ::/loader \
    ::/loader/entries \
    ::/images \
    ::/images/pxeboot

mcopy -i "${ESP_IMG}" "${ESP_STAGING}/${BOOT_EFI_DEST}"                        ::/"${BOOT_EFI_DEST}"
mcopy -i "${ESP_IMG}" "${ESP_STAGING}/loader/loader.conf"                       ::/loader/loader.conf
mcopy -i "${ESP_IMG}" "${ESP_STAGING}/loader/entries/xfce-linux-live.conf"      ::/loader/entries/xfce-linux-live.conf
mcopy -i "${ESP_IMG}" "${ESP_STAGING}/images/pxeboot/vmlinuz"                   ::/images/pxeboot/vmlinuz
mcopy -i "${ESP_IMG}" "${ESP_STAGING}/images/pxeboot/initrd.img"                ::/images/pxeboot/initrd.img

mkdir -p "${ISO_ROOT}/EFI/BOOT"
cp "${BOOT_EFI_SRC}" "${ISO_ROOT}/${BOOT_EFI_DEST}"
echo ">>> EFI fallback: ${BOOT_EFI_DEST} added to ISO root"

mkdir -p "${ISO_ROOT}/images/pxeboot" "${ISO_ROOT}/boot/grub"
cp "${VMLINUZ}" "${ISO_ROOT}/images/pxeboot/vmlinuz"
cp "${INITRD}"  "${ISO_ROOT}/images/pxeboot/initrd.img"
cat > "${ISO_ROOT}/boot/grub/loopback.cfg" << EOF
menuentry "Brussels Live (TunaOS)" {
    linux /images/pxeboot/vmlinuz root=live:CDLABEL=${LABEL} rd.live.image rd.live.overlay.overlayfs=1 enforcing=0 quiet console=ttyS0,115200n8 console=ttyAMA0,115200n8 rd.xfce.isofile=\${iso_path}
    initrd /images/pxeboot/initrd.img
}
EOF
echo ">>> Loopback boot metadata added to ISO root"

echo ">>> Copying squashfs..."
cp "${SQUASHFS_SRC}" "${ISO_ROOT}/LiveOS/squashfs.img"
echo ">>> Squashfs: $(du -sh "${ISO_ROOT}/LiveOS/squashfs.img" | cut -f1)"

echo ">>> Assembling ISO..."
xorriso -as mkisofs \
    -iso-level 3 \
    -r \
    -J --joliet-long \
    -V "${LABEL}" \
    --efi-boot EFI/efi.img \
    -efi-boot-part \
    --efi-boot-image \
    -o "${OUTPUT_ISO}" \
    "${ISO_ROOT}"

implantisomd5 "${OUTPUT_ISO}" 2>/dev/null || true

echo ">>> Partition layout:"
xorriso -indev "${OUTPUT_ISO}" -report_system_area plain 2>/dev/null | \
    grep -E '^(System area|ISO image size|MBR|GPT|Partition)' || true
xorriso -indev "${OUTPUT_ISO}" -report_system_area plain 2>/dev/null | \
    grep 'System area summary' | grep -q 'protective' && \
    echo ">>> Protective MBR + GPT: OK" || \
    echo ">>> WARNING: protective MBR not found — USB may not boot on older firmware"

echo ">>> Done: ${OUTPUT_ISO} ($(du -sh "${OUTPUT_ISO}" | cut -f1))"
