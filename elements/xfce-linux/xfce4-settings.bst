kind: meson
description: |
  Settings daemon and configuration dialogs for XFCE (tuna-os/xfce-linux#158).

build-depends:
# (xmllint)
- freedesktop-sdk.bst:components/libxml2.bst
# meson.build: find_program('sed'/'xmllint', required: true)
- freedesktop-sdk.bst:components/sed.bst
- freedesktop-sdk.bst:public-stacks/buildsystem-meson.bst
- freedesktop-sdk.bst:components/gettext.bst
- freedesktop-sdk.bst:components/wayland-protocols.bst
- freedesktop-sdk.bst:components/wayland.bst
- xfce-linux/xfce4-dev-tools.bst

depends:
- freedesktop-sdk.bst:public-stacks/runtime-minimal.bst
- freedesktop-sdk.bst:components/gtk3.bst
- freedesktop-sdk.bst:components/glib.bst
- freedesktop-sdk.bst:components/libnotify.bst
- freedesktop-sdk.bst:components/fontconfig.bst
- freedesktop-sdk.bst:components/wayland.bst
- freedesktop-sdk.bst:components/xorg-lib-x11.bst
- freedesktop-sdk.bst:components/xorg-lib-xcursor.bst
- freedesktop-sdk.bst:components/xorg-lib-xi.bst
- freedesktop-sdk.bst:components/xorg-lib-xrandr.bst
- freedesktop-sdk.bst:components/xorg-lib-xext.bst
- gnome-build-meta.bst:core-deps/upower.bst
- gnome-build-meta.bst:core-deps/libcanberra.bst
- xfce-linux/libxfce4util.bst
- xfce-linux/libxfce4ui.bst
- xfce-linux/xfconf.bst
- xfce-linux/garcon.bst
- xfce-linux/exo.bst
- xfce-linux/libxfce4windowing.bst
- xfce-linux/gtk-layer-shell.bst

sources:
- kind: git_repo
  url: xfce:xfce/xfce4-settings.git
  track: xfce4-settings-4.21.*
  ref: xfce4-settings-4.21.3-0-gaacc6077e924fc0947b906b5a45e1d86526bb6a1
# git_repo does not fetch submodules; the meson build reads these protocol XMLs.
- kind: git_module
  url: freedesktop:wlroots/wlr-protocols.git
  path: protocols/wlr-protocols
  ref: 4264185db3b7e961e7f157e1cc4fd0ab75137568
- kind: git_module
  url: xfce:xfce/xfce-wayland-protocols.git
  path: protocols/xfce-wayland-protocols
  ref: 68affb31c14127bf6c356a7a8ff9cb62cf44da4c

# Fail the build instead of silently dropping Wayland support: these
# features are "auto" upstream and switch off when gtk-layer-shell is absent.
variables:
  meson-local: >-
    -Dwayland=enabled
    -Dgtk-layer-shell=enabled
