kind: meson
description: |
  Application finder for the XFCE desktop environment (tuna-os/xfce-linux#158).

build-depends:
- freedesktop-sdk.bst:public-stacks/buildsystem-meson.bst
- freedesktop-sdk.bst:components/gettext.bst
- xfce-linux/xfce4-dev-tools.bst

depends:
- freedesktop-sdk.bst:public-stacks/runtime-minimal.bst
- freedesktop-sdk.bst:components/gtk3.bst
- freedesktop-sdk.bst:components/glib.bst
- xfce-linux/libxfce4util.bst
- xfce-linux/libxfce4ui.bst
- xfce-linux/xfconf.bst
- xfce-linux/garcon.bst

sources:
- kind: git_repo
  url: xfce:xfce/xfce4-appfinder.git
  track: xfce4-appfinder-*
  ref: xfce4-appfinder-4.21.1-0-g1ce6be94d8bc0abdd8fd565a55133a1be90496b8
