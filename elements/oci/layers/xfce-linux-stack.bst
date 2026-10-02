kind: stack
description: XFCE Linux stack — freedesktop-sdk base plus XFCE desktop

depends:
  # XFCE Linux dependencies and applications
  - xfce-linux/deps.bst
  # gnome-build-meta gnomeos stack (provides freedesktop-sdk base)
  - gnome-build-meta.bst:oci/gnomeos/stack.bst

public:
  bst:
    integration-commands:
      # Wipe /var (may contain build-time state) and recreate with correct structure
      - rm -rfv /home /root /opt /mnt /srv /var
      - mkdir -p /var/home /var/roothome /var/opt /var/mnt /var/srv /var/tmp
      - ln -s var/home /home
      - ln -s var/roothome /root
      - ln -s var/opt /opt
      - ln -s var/mnt /mnt
      - ln -s var/srv /srv
      # Disable GNOME services that interfere with XFCE
      - systemctl disable gnome-initial-setup || true
      - systemctl enable gdm || true
      # Skip GNOME Initial Setup for new users
      - mkdir -p /etc/skel/.config
      - touch /etc/skel/.config/gnome-initial-setup-done
      # Force remove initial-setup autostart
      - rm -f /usr/share/applications/gnome-initial-setup.desktop
      - rm -f /etc/xdg/autostart/gnome-initial-setup.desktop
      - rm -f /usr/share/gnome-session/sessions/gnome-initial-setup.session
      # Configure GDM for XFCE
      - mkdir -p /etc/gdm
      - |
        cat > /etc/gdm/custom.conf <<EOF
        [daemon]
        AutomaticLoginEnable=True
        AutomaticLogin=xfce
        DefaultSession=xfwl4

        [debug]
        Enable=true
        EOF
      # Set default session for xfce user
      - mkdir -p /var/lib/AccountsService/users
      - |
        cat > /var/lib/AccountsService/users/xfce <<EOF
        [User]
        Session=xfwl4
        Icon=/usr/share/pixmaps/faces/user-generic.png
        SystemAccount=false
        EOF
      # Enable SSH
      #
      # No authorized_keys and no PermitRootLogin override are baked in here.
      # A key committed to this element is a key in every published image, so
      # whoever holds the private half can log in as root on every machine
      # that installs xfce-linux; an image cannot rotate or revoke it, and
      # `PermitRootLogin yes` additionally re-enabled root password
      # authentication on top of the empty root password this image ships.
      #
      # sshd stays enabled, and OpenSSH's default PermitRootLogin
      # (prohibit-password) still accepts a root login by key. To reach a VM
      # over SSH, add your own public key to the deployment instead, for
      # example:
      #
      #   just vm-ip xfce-linux
      #   ssh-copy-id root@<ip>          # once, from the console session
      #
      # or drop a key into /root/.ssh/authorized_keys from the live session
      # before first boot.
      - systemctl enable sshd || true
