#!/usr/bin/bash
# scripts/plain-install-qemu.sh
# Run fisherman with a plain (unencrypted) recipe via SSH into the live QEMU VM.
# Uses shared orchestration from lib-install-qemu.sh.

set -euo pipefail

if [[ $# -lt 4 ]]; then
	echo "Usage: $0 <target> <ssh_port> <monitor_live_socket> <fisher_repo>" >&2
	exit 1
fi

TARGET="$1"
SSH_PORT="$2"
MONITOR_LIVE="$3"
FISHER_REPO="$4"

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

# Generate recipe with plain (no encryption) config
RECIPE_TMP=$(mktemp /tmp/plain-recipe-XXXXXX.json)
trap 'rm -f "${RECIPE_TMP}"' EXIT

if [[ "${COMPOSEFS_BACKEND}" == "true" ]]; then
	# Composefs path (dakota): install from the embedded media OCI layout.
	printf '{\n  "disk": "%s",\n  "filesystem": "%s",\n  "image": "%s",\n  "composeFsBackend": true,\n  "bootloader": "%s",\n  "hostname": "xfce-linux-plain-test",\n  "encryption": {"type": "none"},\n  "flatpaks": []\n}\n' \
		"${DISK}" "${FILESYSTEM}" "${INSTALL_IMAGE}" "${BOOTLOADER}" >"${RECIPE_TMP}"
else
	# Ostree path (stable, lts): bootcDirect — fisherman runs bootc natively.
	# Empty image triggers bootcDirect; targetImgref sets the day-2 rebase ref.
	printf '{\n  "disk": "%s",\n  "filesystem": "%s",\n  "image": "",\n  "targetImgref": "%s",\n  "composeFsBackend": false,\n  "bootloader": "%s",\n  "hostname": "xfce-linux-plain-test",\n  "encryption": {"type": "none"},\n  "flatpaks": []\n}\n' \
		"${DISK}" "${FILESYSTEM}" "${PAYLOAD_IMAGE}" "${BOOTLOADER}" >"${RECIPE_TMP}"
fi

# Execute install
lib_execute_install "${RECIPE_TMP}" "/tmp/plain-recipe.json"

# Patch BLS entries for dual serial+VT console. systemd stops its status
# output on the console when the Type=idle serial getty takes the console,
# which can occur before GDM starts. Forward the journal to the console so
# that "Started gdm.service" always reaches the serial log that
# plain-wait-boot reads.
echo "Patching BLS entries to enable dual serial+VT console and journal forwarding..." >&2
$SSH 'sudo bash -c "
    set -euo pipefail
    BOOT_PART=\"/dev/vda1\"
    if ls /dev/vda3 >/dev/null 2>&1; then
        echo \"Detected 3 partitions layout (separate boot partition for GRUB)\"
        BOOT_PART=\"/dev/vda2\"
    fi
    TMP=\$(mktemp -d)
    trap \"umount \$TMP 2>/dev/null || true; rmdir \$TMP\" EXIT
    mount \"\$BOOT_PART\" \$TMP
    COUNT=0
    for entry in \$TMP/loader/entries/*.conf \$TMP/EFI/loader/entries/*.conf; do
        [[ -f \"\$entry\" ]] || continue
        if grep -q \"^options \" \"\$entry\" && ! grep -q \"console=tty0\" \"\$entry\"; then
            sed -i \"s|^options .*|& console=tty0 console=ttyS0 systemd.journald.forward_to_console=1|\" \"\$entry\"
            COUNT=\$((COUNT+1))
            echo \"  patched: \$(basename \$entry)\"
        fi
    done
    echo \"BLS patch: \$COUNT entries updated\"
"'

# Shutdown QEMU
lib_shutdown_qemu
