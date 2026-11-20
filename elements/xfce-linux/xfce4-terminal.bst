kind: meson
description: |
  Terminal emulator for the XFCE desktop environment (tuna-os/xfce-linux#158).

build-depends:
# meson.build: find_program('xsltproc', required: true), for the man page,
# which uses the DocBook manpages stylesheet via the XML catalog.
- freedesktop-sdk.bst:components/libxslt.bst
- freedesktop-sdk.bst:components/docbook-xsl.bst
- freedesktop-sdk.bst:public-stacks/buildsystem-meson.bst
- freedesktop-sdk.bst:components/gettext.bst
- xfce-linux/xfce4-dev-tools.bst

depends:
- freedesktop-sdk.bst:public-stacks/runtime-minimal.bst
- freedesktop-sdk.bst:components/gtk3.bst
- freedesktop-sdk.bst:components/glib.bst
- freedesktop-sdk.bst:components/xorg-lib-x11.bst
- xfce-linux/vte-gtk3.bst
- xfce-linux/libxfce4util.bst
- xfce-linux/libxfce4ui.bst
- xfce-linux/xfconf.bst
- xfce-linux/gtk-layer-shell.bst

sources:
- kind: git_repo
  url: xfce:apps/xfce4-terminal.git
  track: xfce4-terminal-*
  ref: xfce4-terminal-1.2.0-0-gbcc92696a1526b85875f03c21b265bd376bce00d

# Fail the build instead of silently dropping Wayland support: these
# features are "auto" upstream and switch off when gtk-layer-shell is absent.
variables:
  meson-local: >-
    -Dwayland=enabled
    -Dgtk-layer-shell=enabled
