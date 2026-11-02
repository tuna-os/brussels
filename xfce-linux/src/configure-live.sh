#!/usr/bin/bash
# Live-environment setup for the xfce-linux ISO installer image.
#
# Runs inside the final xfce-linux container stage with:
#   --cap-add sys_admin --security-opt label=disable
#
# This script handles: live user, GDM autologin into XFCE Wayland session,
# tuna-installer autostart, and live-environment hardening.

set -exo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── VERSION_ID ────────────────────────────────────────────────────────────────
if grep -q '^VERSION_ID=' /usr/lib/os-release 2>/dev/null; then
    sed -i 's/^VERSION_ID=.*/VERSION_ID=latest/' /usr/lib/os-release
else
    echo 'VERSION_ID=latest' >> /usr/lib/os-release
fi

# ── Live user ─────────────────────────────────────────────────────────────────
# Create or ensure liveuser exists with no password
if ! getent passwd liveuser >/dev/null 2>&1; then
    # Try to create with UID 1000, but fall back to auto-assign if taken
    useradd --create-home --uid 1000 --user-group \
        --comment "Live User" liveuser 2>/dev/null || \
    useradd --create-home --user-group \
        --comment "Live User" liveuser
fi
# Remove password for passwordless login
passwd --delete liveuser 2>/dev/null || true

# Debug builds: enable SSH and root access for testing.
if [[ "${DEBUG:-0}" == "1" ]]; then
    echo "liveuser:live" | chpasswd
    passwd --unlock root
    echo "root:root" | chpasswd

    mkdir -p /etc/systemd/system-preset
    echo "enable sshd.service" > /etc/systemd/system-preset/90-live-debug.preset
    mkdir -p /etc/systemd/system/multi-user.target.wants
    ln -sf /usr/lib/systemd/system/sshd.service \
        /etc/systemd/system/multi-user.target.wants/sshd.service

    cat >> /etc/ssh/sshd_config << 'SSHEOF'
PermitEmptyPasswords no
PasswordAuthentication yes
PermitRootLogin yes
SSHEOF

    mkdir -p /etc/firewalld/zones
    cat > /etc/firewalld/zones/public.xml << 'FWEOF'
<?xml version="1.0" encoding="utf-8"?>
<zone>
  <short>Public</short>
  <service name="ssh"/>
  <service name="mdns"/>
  <service name="dhcpv6-client"/>
</zone>
FWEOF

    cat > /usr/lib/systemd/system/debug-ssh-banner.service << 'BANNEREOF'
[Unit]
Description=Print SSH connection info to serial console
After=sshd.service network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/bin/bash -c '\
  IP=$(hostname -I | awk "{print \$1}"); \
  echo ""; \
  echo "========================================"; \
  echo " DEBUG SSH READY"; \
  echo " ssh liveuser@${IP:-<no-ip>}  (password: live)"; \
  echo " ssh root@${IP:-<no-ip>}      (password: root)"; \
  echo "========================================"; \
  echo ""'
StandardOutput=journal+console

[Install]
WantedBy=multi-user.target
BANNEREOF
    systemctl enable debug-ssh-banner.service
fi

# Passwordless sudo for liveuser
echo 'liveuser ALL=(ALL) NOPASSWD: ALL' > /etc/sudoers.d/liveuser
chmod 0440 /etc/sudoers.d/liveuser

# ── GNOME initial-setup skip ──────────────────────────────────────────────────
mkdir -p /home/liveuser/.config
touch /home/liveuser/.config/gnome-initial-setup-done
chown -R liveuser:liveuser /home/liveuser/.config

# ── GDM autologin into XFCE Wayland session ───────────────────────────────────
# xfce-linux ships xfce-wayland as the default GDM session.
# DefaultSession must be set so GDM launches XFCE and not GNOME.
mkdir -p /etc/gdm
cat > /etc/gdm/custom.conf << 'GDMEOF'
[daemon]
AutomaticLoginEnable=True
AutomaticLogin=liveuser
DefaultSession=xfce-wayland
WaylandEnable=True
GDMEOF

# Tell AccountsService that liveuser should use the xfce-wayland session.
# Without this, GDM may fall back to whatever session was last used globally.
mkdir -p /var/lib/AccountsService/users
cat > /var/lib/AccountsService/users/liveuser << 'ACEOF'
[User]
Session=xfce-wayland
XSession=xfce-wayland
SystemAccount=false
ACEOF

# ── Mask sleep/suspend ────────────────────────────────────────────────────────
systemctl mask sleep.target suspend.target hibernate.target hybrid-sleep.target

# ── /var/tmp tmpfs ────────────────────────────────────────────────────────────
cat > /usr/lib/systemd/system/var-tmp.mount << 'UNITEOF'
[Unit]
Description=Large tmpfs for /var/tmp in the live environment

[Mount]
What=tmpfs
Where=/var/tmp
Type=tmpfs
Options=size=8G,nr_inodes=1m

[Install]
WantedBy=local-fs.target
UNITEOF
systemctl enable var-tmp.mount

# ── Live-ready marker service ─────────────────────────────────────────────────
# CI boot verification greps for XFCE_LINUX_LIVE_READY in the serial log.
cat > /usr/lib/systemd/system/live-ready.service << 'LREOF'
[Unit]
Description=Live environment ready marker
After=display-manager.service
Requires=display-manager.service

[Service]
Type=oneshot
ExecStart=/bin/echo XFCE_LINUX_LIVE_READY
StandardOutput=tty
TTYPath=/dev/ttyS0

[Install]
WantedBy=multi-user.target
LREOF
systemctl enable live-ready.service

# fisherman scratch space
mkdir -p /var/fisherman-tmp

# ── Installer configuration ───────────────────────────────────────────────────
mkdir -p /etc/bootc-installer
cp "$SCRIPT_DIR/etc/bootc-installer/images.json" /etc/bootc-installer/images.json
cp "$SCRIPT_DIR/etc/bootc-installer/recipe.json"  /etc/bootc-installer/recipe.json
touch /etc/bootc-installer/live-iso-mode

# The live root is a writable overlay over squashfs. Fisherman requires the
# actual OCI source filesystem to be read-only, not merely backed by squashfs.
cat > /usr/lib/systemd/system/usr-lib-tunaos-payload.mount << 'PAYLOADEOF'
[Unit]
Description=Read-only Brussels installation payload
Before=display-manager.service live-ready.service

[Mount]
What=/usr/lib/tunaos/payload
Where=/usr/lib/tunaos/payload
Type=none
Options=bind,ro

[Install]
RequiredBy=local-fs.target
PAYLOADEOF
systemctl enable usr-lib-tunaos-payload.mount

# The frontend catalog and fisherman share the embedded media binding.
mkdir -p /etc/tuna-installer
cp "$SCRIPT_DIR/etc/bootc-installer/images.json" /etc/tuna-installer/images.json

# ── Installer autostart (XFCE variant) ────────────────────────────────────────
# org.tunaos.InstallerXfce is installed from the tuna-os remote by
# install-flatpaks.sh; it reads /etc/tuna-installer/ config (INSTALLER-FRONTENDS.md).
INSTALLER_APP_ID="org.tunaos.InstallerXfce"

mkdir -p /etc/xdg/autostart
cat > /etc/xdg/autostart/tuna-installer.desktop << DTEOF
[Desktop Entry]
Name=Brussels Installer
Exec=flatpak run ${INSTALLER_APP_ID}
Icon=brussels-logo
Terminal=false
Type=Application
NotShowIn=KDE;
DTEOF

mkdir -p /usr/share/applications
cat > /usr/share/applications/xfce-linux-installer.desktop << DTEOF
[Desktop Entry]
Name=Brussels Installer
Comment=Install Brussels by TunaOS to your computer
Exec=flatpak run ${INSTALLER_APP_ID}
Icon=brussels-logo
Type=Application
Categories=System;
NoDisplay=false
DTEOF

# ── Polkit for live installer ─────────────────────────────────────────────────
# Frontends escalate via `flatpak-spawn --host pkexec /usr/local/bin/fisherman`;
# expose the flatpak-bundled binary there.
FISHERMAN_BIN=$(find /var/lib/flatpak/app/${INSTALLER_APP_ID} -path '*/files/bin/fisherman' -type f 2>/dev/null | head -1)
if [ -n "$FISHERMAN_BIN" ]; then
    mkdir -p /usr/local/bin
    ln -sf "${FISHERMAN_BIN}" /usr/local/bin/fisherman
else
    echo "WARNING: fisherman not found inside ${INSTALLER_APP_ID}" >&2
fi

mkdir -p /usr/share/polkit-1/actions
cat > /usr/share/polkit-1/actions/org.tunaos.Installer.policy << 'POLICYEOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE policyconfig PUBLIC
  "-//freedesktop//DTD PolicyKit Policy Configuration 1.0//EN"
  "http://www.freedesktop.org/standards/PolicyKit/1/policyconfig.dtd">
<policyconfig>
  <action id="org.tunaos.Installer.install">
    <description>Install an operating system to disk</description>
    <message>Authentication is required to install an operating system</message>
    <icon_name>drive-harddisk</icon_name>
    <defaults>
      <allow_any>no</allow_any>
      <allow_inactive>no</allow_inactive>
      <allow_active>yes</allow_active>
    </defaults>
    <annotate key="org.freedesktop.policykit.exec.path">/usr/local/bin/fisherman</annotate>
    <annotate key="org.freedesktop.policykit.exec.allow_gui">true</annotate>
  </action>
</policyconfig>
POLICYEOF

mkdir -p /etc/polkit-1/rules.d
cat > /etc/polkit-1/rules.d/99-live-installer.rules << 'EOF'
polkit.addRule(function(action, subject) {
    if ((action.id === "org.freedesktop.policykit.exec" ||
         action.id === "org.tunaos.Installer.install") &&
            subject.user === "liveuser" && subject.local) {
        return polkit.Result.YES;
    }
});
EOF

# ── VFS containers-storage ────────────────────────────────────────────────────
cat > /etc/containers/storage.conf << 'STOREOF'
[storage]
driver = "vfs"
runroot = "/run/containers/storage"
graphroot = "/var/lib/containers/storage"
STOREOF

# ── /etc/hostname ─────────────────────────────────────────────────────────────
mkdir -p /usr/lib/tmpfiles.d
echo 'f /etc/hostname 0644 - - - brussels-live' > /usr/lib/tmpfiles.d/live-hostname.conf
