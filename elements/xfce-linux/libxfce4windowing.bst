kind: meson
description: |
  Windowing environment abstraction library for XFCE (tuna-os/xfce-linux#158).

build-depends:
# meson.build: find_program('python3', required: true)
- freedesktop-sdk.bst:components/python3.bst
- freedesktop-sdk.bst:public-stacks/buildsystem-meson.bst
- freedesktop-sdk.bst:components/gobject-introspection.bst
- freedesktop-sdk.bst:components/vala.bst
- freedesktop-sdk.bst:components/gettext.bst
- freedesktop-sdk.bst:components/wayland-protocols.bst
- freedesktop-sdk.bst:components/wayland.bst
- xfce-linux/xfce4-dev-tools.bst

depends:
- freedesktop-sdk.bst:public-stacks/runtime-minimal.bst
- freedesktop-sdk.bst:components/gtk3.bst
- freedesktop-sdk.bst:components/glib.bst
- freedesktop-sdk.bst:components/wayland.bst
- freedesktop-sdk.bst:components/libdisplay-info.bst
- freedesktop-sdk.bst:components/xorg-lib-x11.bst
- freedesktop-sdk.bst:components/xorg-lib-xrandr.bst
- xfce-linux/libxfce4util.bst

sources:
- kind: git_repo
  url: xfce:xfce/libxfce4windowing.git
  track: libxfce4windowing-*
  ref: libxfce4windowing-4.20.7-0-ge288652b65a103c64161307281116b838c5df643
# git_repo does not fetch submodules; the meson build reads these protocol XMLs.
- kind: git_module
  url: freedesktop:wlroots/wlr-protocols.git
  path: protocols/wlr-protocols
  ref: 4264185db3b7e961e7f157e1cc4fd0ab75137568
- kind: git_module
  url: xfce:xfce/xfce-wayland-protocols.git
  path: protocols/xfce-wayland-protocols
  ref: 55dbf3e3d2a91b525c528c0dd4c1a7805a99364b
