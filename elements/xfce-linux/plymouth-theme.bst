kind: manual
description: >-
  Brussels Plymouth boot splash with original TunaOS artwork.
  The GNOME OS parent supplies the bgrt/spinner theme; this element
  replaces its watermark and retains the upstream theme implementation.

sources:
- kind: local
  path: branding/brussels

build-depends:
- gnome-build-meta.bst:freedesktop-sdk.bst:public-stacks/runtime-minimal.bst
- gnome-build-meta.bst:freedesktop-sdk.bst:components/librsvg.bst

# Depend on the GNOME theme so this element stages after it in the compose
# and our watermark/defaults win the overlap.
runtime-depends:
- gnome-build-meta.bst:gnomeos-deps/plymouth-gnome-theme.bst

variables:
  strip-binaries: ''

config:
  install-commands:
  - |
    # Render the original TunaOS product mark at splash size.
    rsvg-convert -w 256 -h 256 brussels-logo.svg -o watermark.png
    install -Dm644 watermark.png "%{install-root}%{datadir}/plymouth/themes/spinner/watermark.png"
    install -Dm644 watermark.png "%{install-root}%{datadir}/pixmaps/brussels-boot-logo.png"
    install -d "%{install-root}%{datadir}/plymouth"
    cat > "%{install-root}%{datadir}/plymouth/plymouthd.defaults" << 'EOF'
    [Daemon]
    Theme=bgrt
    ShowDelay=0
    DeviceTimeout=8
    EOF
  - |
    # bootc-installed systems: boot with `splash` so plymouth shows the
    # graphical splash and LUKS passphrase prompt. Deliberately no `quiet` —
    # CI's serial-log assertions depend on boot messages.
    install -d "%{install-root}/usr/lib/bootc/kargs.d"
    printf 'kargs = ["splash"]\n' > "%{install-root}/usr/lib/bootc/kargs.d/50-splash.toml"

public:
  bst:
    overlap-whitelist:
    - '%{datadir}/plymouth/plymouthd.defaults'
    - '%{datadir}/plymouth/themes/spinner/watermark.png'
