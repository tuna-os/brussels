kind: meson
description: |
  libwlembed — embedded Wayland compositor library by the xfwl4 author.

  xfce4-screensaver's Wayland backend (-Dwayland=enabled) needs
  libwlembed-0 and libwlembed-gtk3-0 to embed its lock dialog. libwlembed
  has no release tag yet, so this element pins a commit of the upstream
  repository (gitlab.xfce.org/kelnos/libwlembed). Move to a tag when one
  exists; docs/xfce-component-set.md records this exception.

build-depends:
- freedesktop-sdk.bst:public-stacks/buildsystem-meson.bst
- freedesktop-sdk.bst:components/wayland-protocols.bst
- xfce-linux/xfce4-dev-tools.bst

depends:
- freedesktop-sdk.bst:public-stacks/runtime-minimal.bst
- freedesktop-sdk.bst:components/glib.bst
- freedesktop-sdk.bst:components/gtk3.bst
- freedesktop-sdk.bst:components/wayland.bst
- freedesktop-sdk.bst:components/libxkbcommon.bst
- xfce-linux/gtk-layer-shell.bst

sources:
- kind: git_repo
  url: xfce:kelnos/libwlembed.git
  track: main
  ref: f39b03275703b88c5ab100e71f5bb3fbc1794090
# git_repo does not fetch submodules; meson falls back to this copy when
# no wlr-protocols.pc is installed.
- kind: git_module
  url: freedesktop:wlroots/wlr-protocols.git
  path: protocol/wlr-protocols
  ref: 4264185db3b7e961e7f157e1cc4fd0ab75137568

variables:
  meson-local: >-
    -Dgtk3=enabled
    -Dgtk3-layer-shell=enabled
    -Dintrospection=false
    -Dexamples=false
