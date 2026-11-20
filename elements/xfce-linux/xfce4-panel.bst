kind: meson
description: |
  Next-generation panel for the XFCE desktop environment (tuna-os/xfce-linux#158).

build-depends:
- freedesktop-sdk.bst:public-stacks/buildsystem-meson.bst
- freedesktop-sdk.bst:components/gobject-introspection.bst
- freedesktop-sdk.bst:components/vala.bst
- freedesktop-sdk.bst:components/gettext.bst
- xfce-linux/xfce4-dev-tools.bst

depends:
- freedesktop-sdk.bst:public-stacks/runtime-minimal.bst
- freedesktop-sdk.bst:components/gtk3.bst
- freedesktop-sdk.bst:components/glib.bst
- freedesktop-sdk.bst:components/cairo.bst
- freedesktop-sdk.bst:components/wayland.bst
- freedesktop-sdk.bst:components/xorg-lib-x11.bst
- freedesktop-sdk.bst:components/xorg-lib-xext.bst
- xfce-linux/libxfce4util.bst
- xfce-linux/libxfce4ui.bst
# libxfce4session-client-1 >= 4.21.2 (new in the 4.21.2 session release)
- xfce-linux/xfce4-session.bst
- xfce-linux/xfconf.bst
- xfce-linux/garcon.bst
- xfce-linux/libxfce4windowing.bst
- xfce-linux/gtk-layer-shell.bst

sources:
- kind: git_repo
  url: xfce:xfce/xfce4-panel.git
  track: xfce4-panel-4.21.*
  ref: xfce4-panel-4.21.3-0-g76eac3b790ba72481f6e39f88e51589f38605efb

# Fail the build instead of silently dropping Wayland support: these
# features are "auto" upstream and switch off when gtk-layer-shell is absent.
variables:
  meson-local: >-
    -Dwayland=enabled
    -Dgtk-layer-shell=enabled
