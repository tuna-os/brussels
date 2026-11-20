kind: meson
description: |
  Freedesktop.org compliant menu library for XFCE (tuna-os/xfce-linux#158).

build-depends:
- freedesktop-sdk.bst:public-stacks/buildsystem-meson.bst
- freedesktop-sdk.bst:components/gobject-introspection.bst
- freedesktop-sdk.bst:components/gettext.bst
- xfce-linux/xfce4-dev-tools.bst

depends:
- freedesktop-sdk.bst:public-stacks/runtime-minimal.bst
- freedesktop-sdk.bst:components/gtk3.bst
- freedesktop-sdk.bst:components/glib.bst
- xfce-linux/libxfce4util.bst
- xfce-linux/libxfce4ui.bst

sources:
- kind: git_repo
  url: xfce:xfce/garcon.git
  track: garcon-*
  ref: garcon-4.21.0-0-g8ffd94b7c6a392501ed66e4c44dcf3b539079caa
