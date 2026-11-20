kind: meson
description: |
  Widget library and keyboard shortcuts for XFCE (tuna-os/xfce-linux#158).

build-depends:
# meson.build: find_program('sed', required: true)
- freedesktop-sdk.bst:components/sed.bst
- freedesktop-sdk.bst:public-stacks/buildsystem-meson.bst
- freedesktop-sdk.bst:components/gobject-introspection.bst
- freedesktop-sdk.bst:components/vala.bst
- freedesktop-sdk.bst:components/gettext.bst
- xfce-linux/xfce4-dev-tools.bst

depends:
- freedesktop-sdk.bst:public-stacks/runtime-minimal.bst
- freedesktop-sdk.bst:components/gtk3.bst
- freedesktop-sdk.bst:components/glib.bst
- freedesktop-sdk.bst:components/libepoxy.bst
- freedesktop-sdk.bst:components/libnotify.bst
- freedesktop-sdk.bst:components/systemd.bst
- freedesktop-sdk.bst:components/xorg-lib-x11.bst
- freedesktop-sdk.bst:components/xorg-lib-sm.bst
- freedesktop-sdk.bst:components/xorg-lib-ice.bst
- gnome-build-meta.bst:core-deps/libgtop.bst
- xfce-linux/libxfce4util.bst
- xfce-linux/xfconf.bst

sources:
- kind: git_repo
  url: xfce:xfce/libxfce4ui.git
  track: libxfce4ui-*
  ref: libxfce4ui-4.21.9-0-g9e5b8a1efbd887821d451bb68d582bdeee2c5e7b
