kind: meson
description: |
  Power manager for the XFCE desktop environment (tuna-os/xfce-linux#158).

build-depends:
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
- freedesktop-sdk.bst:components/polkit.bst
- freedesktop-sdk.bst:components/wayland.bst
- freedesktop-sdk.bst:components/xorg-lib-x11.bst
- freedesktop-sdk.bst:components/xorg-lib-xext.bst
- freedesktop-sdk.bst:components/xorg-lib-xrandr.bst
- gnome-build-meta.bst:core-deps/upower.bst
- xfce-linux/libxfce4util.bst
- xfce-linux/libxfce4ui.bst
- xfce-linux/xfconf.bst
- xfce-linux/xfce4-panel.bst

sources:
- kind: git_repo
  url: xfce:xfce/xfce4-power-manager.git
  track: xfce4-power-manager-*
  ref: xfce4-power-manager-4.21.1-0-gf6e83d2c95a7adf58cf62b5b69c50ac11a51a2d9
# git_repo does not fetch submodules; the meson build reads these protocol XMLs.
- kind: git_module
  url: freedesktop:wlroots/wlr-protocols.git
  path: protocols/wlr-protocols
  ref: 4264185db3b7e961e7f157e1cc4fd0ab75137568
