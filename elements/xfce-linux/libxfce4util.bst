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
  track: libxfce4util-*
  ref: libxfce4util-4.20.1-0-gfe1b3c88e4e0cb45eb490d11dbc7f9cdd83664d9
