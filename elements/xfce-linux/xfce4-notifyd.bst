kind: meson
description: |
  Notification daemon for the XFCE desktop environment (tuna-os/xfce-linux#158).

build-depends:
- freedesktop-sdk.bst:public-stacks/buildsystem-meson.bst
- freedesktop-sdk.bst:components/gettext.bst
- xfce-linux/xfce4-dev-tools.bst

depends:
- freedesktop-sdk.bst:public-stacks/runtime-minimal.bst
- freedesktop-sdk.bst:components/gtk3.bst
- freedesktop-sdk.bst:components/glib.bst
- freedesktop-sdk.bst:components/libnotify.bst
- freedesktop-sdk.bst:components/sqlite.bst
- freedesktop-sdk.bst:components/systemd.bst
- freedesktop-sdk.bst:components/xorg-lib-x11.bst
- gnome-build-meta.bst:core-deps/libcanberra.bst
- xfce-linux/libxfce4util.bst
- xfce-linux/libxfce4ui.bst
- xfce-linux/xfconf.bst
- xfce-linux/xfce4-panel.bst
- xfce-linux/gtk-layer-shell.bst

sources:
- kind: git_repo
  url: xfce:apps/xfce4-notifyd.git
  track: xfce4-notifyd-*
  ref: xfce4-notifyd-0.9.7-0-g9031cd94e173424841b31201d158a766c20059a8

# Fail the build instead of silently dropping Wayland support: these
# features are "auto" upstream and switch off when gtk-layer-shell is absent.
variables:
  meson-local: >-
    -Dwayland=enabled
