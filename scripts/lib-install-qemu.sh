#!/usr/bin/bash
# scripts/lib-install-qemu.sh
# Shared orchestration logic for E2E install tests via fisherman.
# Provides common functions for plain and LUKS-encrypted installs via SSH into
# live QEMU VM.
#
# Sourced by: plain-install-qemu.sh, luks-install-qemu.sh
# Expected environment variables (set by caller):
#   TARGET: path to target directory (contains payload_ref, composefs, bootloader files)
#   SSH_PORT: SSH port for QEMU VM
#   MONITOR_LIVE: path to QEMU monitor socket
#   PAYLOAD_IMAGE: image reference (read from TARGET/payload_ref)
#   RECIPE_JSON: JSON recipe to install (caller must generate with encryption config)
#   RECIPE_PATH: destination path for recipe in /tmp on VM
#   INSTALL_TYPE: string for logging (e.g., "plain" or "LUKS")
#   COMPOSEFS_BACKEND: true/false (read from TARGET/composefs)
#   BOOTLOADER: bootloader type (read from TARGET/bootloader)
#   DISK: disk device (typically /dev/vda)
#   FILESYSTEM: filesystem type (typically btrfs)

set -euo pipefail

# ─────────────────────────────────────────────────────────────────────────
# SSH/SCP Configuration
# ─────────────────────────────────────────────────────────────────────────

SSH_OPTS="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR -o ConnectTimeout=5 -o PreferredAuthentications=password -o ServerAliveInterval=30 -o ServerAliveCountMax=20"
SSH="sshpass -p live ssh $SSH_OPTS liveuser@127.0.0.1 -p ${SSH_PORT}"
SCP="sshpass -p live scp $SSH_OPTS -P ${SSH_PORT}"

# ─────────────────────────────────────────────────────────────────────────
# Common Image Resolution
# ─────────────────────────────────────────────────────────────────────────

lib_resolve_install_image() {
	# Fail before touching a disk if the immutable media contract is absent.
	$SSH "sudo test -r /etc/bootc-installer/media-input.json"
	$SSH "sudo test -r /usr/lib/tunaos/payload/index.json"
	# An empty recipe image selects fisherman's verified, media-bound source.
	printf ''
}

# ─────────────────────────────────────────────────────────────────────────
# Scratch Disk Mount
# ─────────────────────────────────────────────────────────────────────────

lib_mount_scratch_disk() {
	echo "Mounting scratch disk (/dev/vdb) over /var/tmp..." >&2
	$SSH 'sudo bash -c "
    mkfs.ext4 -F /dev/vdb >/dev/null
    umount /var/tmp 2>/dev/null || true
    mount /dev/vdb /var/tmp
    echo \"/var/tmp is now disk-backed on /dev/vdb\"
"'
}

# ─────────────────────────────────────────────────────────────────────────
# Shipped fisherman (composefs and native bootc paths)
# ─────────────────────────────────────────────────────────────────────────

lib_execute_install() {
	local recipe_tmp="$1"
	local recipe_dest="$2"
	echo "=== Live desktop/session diagnostics ===" >&2
	$SSH 'sudo journalctl -b --no-pager | grep -Ev "TRACE|xfconf_backend_perchannel" | grep -E "xfwl4|xfce4-session|xfce4-panel|xfdesktop|tuna|ERROR|WARN|PANIC|panic" | tail -n 100' >&2
	
	$SCP "${recipe_tmp}" liveuser@127.0.0.1:"${recipe_dest}"
	echo "Uploaded recipe — running fisherman (takes several minutes)..." >&2
	$SSH "sudo /usr/local/bin/fisherman ${recipe_dest}"
}


# ─────────────────────────────────────────────────────────────────────────
# QEMU Monitor Shutdown
# ─────────────────────────────────────────────────────────────────────────

lib_shutdown_qemu() {
	echo "Install complete. Shutting down live QEMU..." >&2
	SOCAT_PREFIX=""
	if ! test -w "${MONITOR_LIVE}" 2>/dev/null; then SOCAT_PREFIX="sudo"; fi
	echo "system_powerdown" | $SOCAT_PREFIX socat - "UNIX-CONNECT:${MONITOR_LIVE}" 2>/dev/null || true
	sleep 5
	echo "quit" | $SOCAT_PREFIX socat - "UNIX-CONNECT:${MONITOR_LIVE}" 2>/dev/null || true
}
