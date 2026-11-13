#!/usr/bin/bash
# scripts/luks-install-qemu.sh
# Run fisherman with LUKS-encrypted recipe via SSH into the live QEMU VM.
# Uses shared orchestration from lib-install-qemu.sh.

set -euo pipefail

if [[ $# -lt 5 ]]; then
	echo "Usage: $0 <target> <luks_passphrase> <ssh_port> <monitor_live_socket> <fisher_repo>" >&2
	exit 1
fi

TARGET="$1"
PASSPHRASE="$2"
SSH_PORT="$3"
MONITOR_LIVE="$4"
FISHER_REPO="$5"

DISK="/dev/vda"
PAYLOAD_IMAGE=$(cat "${TARGET}/payload_ref" | tr -d '[:space:]')

# Source shared library
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib-install-qemu.sh"

# Read target overrides
COMPOSEFS_BACKEND=$(cat "${TARGET}/composefs" 2>/dev/null | tr -d '[:space:]' || echo "true")
BOOTLOADER=$(cat "${TARGET}/bootloader" 2>/dev/null | tr -d '[:space:]' || echo "systemd")

# Normalise "grub" → "grub2" for fisherman's recipe validator.
if [[ "${BOOTLOADER}" == "grub" ]]; then BOOTLOADER="grub2"; fi

# Determine target filesystem
FILESYSTEM="btrfs"

# Resolve install image (offline or network)
INSTALL_IMAGE=$(lib_resolve_install_image)

# Mount scratch disk
lib_mount_scratch_disk

# Generate recipe with LUKS encryption config
RECIPE_TMP=$(mktemp /tmp/luks-recipe-XXXXXX.json)
trap 'rm -f "${RECIPE_TMP}"' EXIT

if [[ "${COMPOSEFS_BACKEND}" == "true" ]]; then
	# Composefs path (dakota): install from the embedded media OCI layout.
	printf '{\n  "disk": "%s",\n  "filesystem": "%s",\n  "image": "%s",\n  "composeFsBackend": true,\n  "bootloader": "%s",\n  "hostname": "xfce-linux-luks-test",\n  "encryption": {"type": "luks-passphrase", "passphrase": "%s"},\n  "flatpaks": []\n}\n' \
		"${DISK}" "${FILESYSTEM}" "${INSTALL_IMAGE}" "${BOOTLOADER}" "${PASSPHRASE}" >"${RECIPE_TMP}"
else
	# Ostree path (stable, lts): bootcDirect — fisherman runs bootc natively.
	# An empty image selects the source bound in media-input.json;
	# targetImgref must equal its day-2 update ref.
	printf '{\n  "disk": "%s",\n  "filesystem": "%s",\n  "image": "",\n  "targetImgref": "%s",\n  "composeFsBackend": false,\n  "bootloader": "%s",\n  "hostname": "xfce-linux-luks-test",\n  "encryption": {"type": "luks-passphrase", "passphrase": "%s"},\n  "flatpaks": []\n}\n' \
		"${DISK}" "${FILESYSTEM}" "${PAYLOAD_IMAGE}" "${BOOTLOADER}" "${PASSPHRASE}" >"${RECIPE_TMP}"
fi

# Execute install
lib_execute_install "${RECIPE_TMP}" "/tmp/luks-recipe.json"

# Patch BLS entries for dual serial+VT console and LUKS unlock
echo "Patching BLS entries to enable dual serial+VT console and LUKS unlock..." >&2
$SSH 'sudo bash -c "
    set -euo pipefail
    BOOT_PART=\"/dev/vda1\"
    LUKS_PART=\"/dev/vda2\"
    if ls /dev/vda3 >/dev/null 2>&1; then
        echo \"Detected 3 partitions layout (separate boot partition for GRUB)\"
        BOOT_PART=\"/dev/vda2\"
        LUKS_PART=\"/dev/vda3\"
    fi
    LUKS_UUID=\$(cryptsetup luksUUID \"\$LUKS_PART\" 2>/dev/null || echo \"\")
    TMP=\$(mktemp -d)
    trap \"umount \$TMP 2>/dev/null || true; rmdir \$TMP\" EXIT
    mount \"\$BOOT_PART\" \$TMP
    COUNT=0
    for entry in \$TMP/loader/entries/*.conf \$TMP/EFI/loader/entries/*.conf; do
        [[ -f \"\$entry\" ]] || continue
        if grep -q \"^options \" \"\$entry\" && ! grep -q \"console=tty0\" \"\$entry\"; then
            if [[ -n \"\$LUKS_UUID\" ]]; then
                sed -i \"s|^options .*|& console=tty0 console=ttyS0 rd.luks.name=\${LUKS_UUID}=root|\" \"\$entry\"
            else
                sed -i \"s|^options .*|& console=tty0 console=ttyS0|\" \"\$entry\"
            fi
            COUNT=\$((COUNT+1))
            echo \"  patched: \$(basename \$entry)\"
        fi
    done
    echo \"BLS patch: \$COUNT entries updated\"
"'

# Shutdown QEMU
lib_shutdown_qemu
