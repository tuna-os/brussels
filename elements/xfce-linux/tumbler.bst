kind: meson
description: |
  D-Bus service for generating thumbnail images (tuna-os/xfce-linux#158).

build-depends:
- freedesktop-sdk.bst:public-stacks/buildsystem-meson.bst
- freedesktop-sdk.bst:components/gettext.bst
- xfce-linux/xfce4-dev-tools.bst

depends:
- freedesktop-sdk.bst:public-stacks/runtime-minimal.bst
- freedesktop-sdk.bst:components/glib.bst
- freedesktop-sdk.bst:components/gdk-pixbuf.bst
- freedesktop-sdk.bst:components/gstreamer.bst
- freedesktop-sdk.bst:components/gstreamer-plugins-base.bst
- freedesktop-sdk.bst:components/freetype.bst
- freedesktop-sdk.bst:components/libpng.bst
- freedesktop-sdk.bst:components/jpeg.bst
- freedesktop-sdk.bst:components/curl.bst
- xfce-linux/libxfce4util.bst

sources:
- kind: git_repo
  url: xfce:xfce/tumbler.git
  track: tumbler-*
  ref: tumbler-4.21.1-0-g821c7fe0a4c99c424f688116143e3d5757b35e5f
