kind: meson
description: |
  GTK3 build of VTE (vte-2.91) for xfce4-terminal (tuna-os/xfce-linux#158).

  gnome-build-meta's core-deps/vte.bst on gnome-50 builds only the GTK4
  widget (-Dgtk3=false), so nothing in either junction provides vte-2.91.
  This element builds the same release with -Dgtk3=true -Dgtk4=false and
  ships only the GTK3 library, headers and pkg-config file. The parts both
  builds install (vte-urlencode-cwd helper, profile.d scripts, systemd
  scope drop-in, translations) come from gnome-build-meta's vte, which is a
  runtime dependency here; shipping them twice would be a fatal overlap.
  Keep the version in step with gnome-build-meta.bst:core-deps/vte.bst.

build-depends:
- freedesktop-sdk.bst:public-stacks/buildsystem-meson.bst
- freedesktop-sdk.bst:components/gettext.bst
- gnome-build-meta.bst:core-deps/fast-float.bst

depends:
- freedesktop-sdk.bst:public-stacks/runtime-minimal.bst
- freedesktop-sdk.bst:components/gtk3.bst
- freedesktop-sdk.bst:components/glib.bst
- freedesktop-sdk.bst:components/fmtlib.bst
- freedesktop-sdk.bst:components/fribidi.bst
- freedesktop-sdk.bst:components/gnutls.bst
- freedesktop-sdk.bst:components/icu.bst
- freedesktop-sdk.bst:components/lz4.bst
- freedesktop-sdk.bst:components/systemd-libs.bst
- gnome-build-meta.bst:core-deps/simdutf.bst
- gnome-build-meta.bst:core-deps/vte.bst

sources:
- kind: tar
  url: gnome_downloads:vte/0.84/vte-0.84.0.tar.xz
  ref: 0414e31583836aeb7878da25f67c515f7e8879917ecc37c92e26b83e8d8fc3e3

variables:
  meson-local: >-
    -Dgtk3=true
    -Dgtk4=false
    -Dapp=false
    -Ddocs=false
    -Dglade=false
    -Dgir=false
    -Dvapi=false

config:
  install-commands:
    (>):
    # Shared with the GTK4 build from gnome-build-meta (see description).
    - rm -rf "%{install-root}%{sysconfdir}/profile.d"
    - rm -rf "%{install-root}%{libexecdir}"
    - rm -rf "%{install-root}%{datadir}/locale"
    - rm -rf "%{install-root}%{prefix}/lib/systemd"
