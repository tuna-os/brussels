kind: script
description: |
  XFCE Linux OCI image — Wayland desktop with xfwl4 compositor.

build-depends:
  - gnome-build-meta.bst:freedesktop-sdk.bst:components/fakecap.bst
  - gnome-build-meta.bst:freedesktop-sdk.bst:components/oci-builder.bst
  - freedesktop-sdk.bst:components/glib.bst
  - gnome-build-meta.bst:core-deps/dconf.bst
  - gnome-build-meta.bst:freedesktop-sdk.bst:vm/prepare-image.bst
  - oci/layers/xfce-linux-init-scripts.bst
  - filename: gnome-build-meta.bst:oci/gnomeos/image.bst
    config:
      location: /parent
  - filename: oci/layers/xfce-linux.bst
    config:
      location: /layer
  - filename: oci/os-release.bst
    config:
      location: /identity

environment:
  LD_PRELOAD: /usr/libexec/fakecap/fakecap.so
  FAKECAP_DB: /fakecap

variables:
  sysroot-seed: a1b2c3d4-e5f6-7890-abcd-ef1234567890

config:
  commands:
    - |
      # Use the repository's stable product identity and codename.
      install -Dm644 /identity/usr/lib/os-release /layer/usr/lib/os-release
    - mkdir /fakecap
    - |
      prepare-image.sh \
         --sysroot /layer \
         --initscripts /initial_scripts \
         --seed "%{sysroot-seed}" \
         --noroot --noboot >/dev/null

    - |
      systemd-sysusers --root /layer

    - |
      # Remove password for xfce and root users for live-style access
      if [ -f /layer/etc/shadow ]; then
        sed -i "s|^xfce:[^:]*:|xfce::|" /layer/etc/shadow
        sed -i "s|^root:[^:]*:|root::|" /layer/etc/shadow
      fi

    - |
      # Skip GNOME Initial Setup for xfce user (use skeleton)
      mkdir -p /layer/etc/skel/.config
      touch /layer/etc/skel/.config/gnome-initial-setup-done

    - |
      # Configure Sudo for xfce user
      mkdir -p /layer/etc/sudoers.d
      echo "xfce ALL=(ALL) NOPASSWD: ALL" > /layer/etc/sudoers.d/xfce
      chmod 440 /layer/etc/sudoers.d/xfce

    - |
      # Force use xfce-wayland as default
      if [ -f /layer/etc/gdm/custom.conf ]; then
        sed -i 's/DefaultSession=.*/DefaultSession=xfce-wayland/' /layer/etc/gdm/custom.conf
      fi

    - |
      glib-compile-schemas /layer/usr/share/glib-2.0/schemas

    # bootc images must not have both /etc and /usr/etc.
    - |
      if [ -d /layer/usr/etc ]; then
        mkdir -p /layer/etc
        cp -a /layer/usr/etc/. /layer/etc/
        rm -rf /layer/usr/etc
      fi

    - |
      dconf update /layer/etc/dconf/db

    - |
      cd "%{install-root}"
      build-oci <<EOF
      mode: oci
      gzip: disabled
      images:
      - os: linux
        architecture: "%{go-arch}"
        parent:
          image: /parent
        layer: /layer
        comment: "Import Brussels layer"
        config:
          Labels:
            'com.github.containers.toolbox': 'true'
            'org.opencontainers.image.title': 'Brussels'
            'org.opencontainers.image.description': 'Brussels by TunaOS: experimental Xfce Wayland desktop with xfwl4'
            'org.opencontainers.image.vendor': 'TunaOS'
            'org.opencontainers.image.licenses': 'GPL-3.0'
            'org.opencontainers.image.url': 'https://github.com/tuna-os/xfce-linux'
            'org.opencontainers.image.source': 'https://github.com/tuna-os/xfce-linux'
            'containers.bootc': '1'
        index-annotations:
          'org.opencontainers.image.ref.name': 'ghcr.io/tuna-os/xfce-linux:latest'
      EOF
