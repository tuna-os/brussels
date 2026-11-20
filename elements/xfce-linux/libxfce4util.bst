kind: meson
description: |
  Basic utility library for the XFCE desktop environment (tuna-os/xfce-linux#158).

build-depends:
- freedesktop-sdk.bst:public-stacks/buildsystem-meson.bst
- freedesktop-sdk.bst:components/gobject-introspection.bst
- freedesktop-sdk.bst:components/vala.bst
- freedesktop-sdk.bst:components/gettext.bst
- xfce-linux/xfce4-dev-tools.bst

depends:
- freedesktop-sdk.bst:public-stacks/runtime-minimal.bst
- freedesktop-sdk.bst:components/glib.bst

sources:
- kind: git_repo
  url: xfce:xfce/libxfce4util.git
  track: libxfce4util-4.21.*
  ref: libxfce4util-4.21.0-0-gaf5f49d889cb55483c36ca8b20f11913da26b325
