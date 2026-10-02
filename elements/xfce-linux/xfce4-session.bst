kind: meson
description: |
  Session manager for the XFCE desktop environment (tuna-os/xfce-linux#158).

build-depends:
- freedesktop-sdk.bst:public-stacks/buildsystem-meson.bst
- freedesktop-sdk.bst:components/gettext.bst
- xfce-linux/xfce4-dev-tools.bst

depends:
- freedesktop-sdk.bst:public-stacks/runtime-minimal.bst
- freedesktop-sdk.bst:components/gtk3.bst
- freedesktop-sdk.bst:components/glib.bst
- freedesktop-sdk.bst:components/polkit.bst
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
  track: xfce4-session-*
  ref: xfce4-session-4.21.1-0-g5681e8b24d192ff572a52f80e9381d6543dfd2e0

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
