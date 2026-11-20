kind: meson
description: |
  Hierarchical configuration system for XFCE (tuna-os/xfce-linux#158).

build-depends:
- freedesktop-sdk.bst:public-stacks/buildsystem-meson.bst
- freedesktop-sdk.bst:components/gobject-introspection.bst
- freedesktop-sdk.bst:components/vala.bst
- freedesktop-sdk.bst:components/gettext.bst
- freedesktop-sdk.bst:components/perl-xml-parser.bst
- xfce-linux/xfce4-dev-tools.bst

depends:
- freedesktop-sdk.bst:public-stacks/runtime-minimal.bst
- freedesktop-sdk.bst:components/glib.bst
- freedesktop-sdk.bst:components/dbus.bst
- xfce-linux/libxfce4util.bst

sources:
- kind: git_repo
  url: xfce:xfce/xfconf.git
  track: xfconf-*
  ref: xfconf-4.21.2-0-ga6f0a7aa9073f9d8a0935cee73c0da52b6e49660
