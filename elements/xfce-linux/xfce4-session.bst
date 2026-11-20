kind: meson
description: |
  Session manager for the XFCE desktop environment (tuna-os/xfce-linux#158).

build-depends:
- freedesktop-sdk.bst:public-stacks/buildsystem-meson.bst
- freedesktop-sdk.bst:components/gettext.bst
# 4.21.2 builds libxfce4session-client with GObject introspection and Vala
# bindings, and generates Wayland protocol code (wayland-scanner).
- freedesktop-sdk.bst:components/gobject-introspection.bst
- freedesktop-sdk.bst:components/vala.bst
- freedesktop-sdk.bst:components/wayland-protocols.bst
# meson.build: find_program('sed', required: true)
- freedesktop-sdk.bst:components/sed.bst
- xfce-linux/xfce4-dev-tools.bst

depends:
- freedesktop-sdk.bst:public-stacks/runtime-minimal.bst
- freedesktop-sdk.bst:components/gtk3.bst
- freedesktop-sdk.bst:components/glib.bst
- freedesktop-sdk.bst:components/polkit.bst
- freedesktop-sdk.bst:components/wayland.bst
- freedesktop-sdk.bst:components/xorg-lib-x11.bst
- freedesktop-sdk.bst:components/xorg-lib-sm.bst
- freedesktop-sdk.bst:components/xorg-lib-ice.bst
- xfce-linux/libxfce4util.bst
- xfce-linux/libxfce4ui.bst
- xfce-linux/xfconf.bst
- xfce-linux/libxfce4windowing.bst
- xfce-linux/gtk-layer-shell.bst

sources:
- kind: git_repo
  url: xfce:xfce/xfce4-session.git
  track: xfce4-session-4.21.*
  ref: xfce4-session-4.21.2-0-g408e2dc9784c687a5728efa006d4d9dd22bc8243

# X11 session management needs iceauth (find_program, required), which
# neither junction provides. This image runs xfwl4 (Wayland), so build
# the session without the X11 backend.
variables:
  meson-local: >-
    -Dwayland=enabled
    -Dgtk-layer-shell=enabled
    -Dx11=disabled

# xfce4-session's own wayland-sessions/xfce-wayland.desktop runs
# `startxfce4 --wayland`, whose default compositor is labwc. This image
# ships xfwl4 instead, and xfwl4 installs its own session entry
# (xfwl4.desktop, which starts xfce4-session itself). Drop the labwc entry
# so the display manager does not offer a session that cannot start.
# The labwc config templates go with it.
config:
  install-commands:
    (>):
    - rm -f "%{install-root}%{datadir}/wayland-sessions/xfce-wayland.desktop"
    - rm -rf "%{install-root}%{datadir}/xfce4/labwc"
