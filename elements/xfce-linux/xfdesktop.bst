kind: meson
description: |
  Desktop manager for the XFCE desktop environment (tuna-os/xfce-linux#158).

build-depends:
- freedesktop-sdk.bst:public-stacks/buildsystem-meson.bst
- freedesktop-sdk.bst:components/gettext.bst
- xfce-linux/xfce4-dev-tools.bst

depends:
- freedesktop-sdk.bst:public-stacks/runtime-minimal.bst
- freedesktop-sdk.bst:components/gtk3.bst
- freedesktop-sdk.bst:components/glib.bst
- freedesktop-sdk.bst:components/libnotify.bst
- freedesktop-sdk.bst:components/libyaml.bst
- freedesktop-sdk.bst:components/gstreamer.bst
- freedesktop-sdk.bst:components/xorg-lib-x11.bst
- xfce-linux/libxfce4util.bst
- xfce-linux/libxfce4ui.bst
# libxfce4session-client-1 >= 4.21.2 (new in the 4.21.2 session release)
- xfce-linux/xfce4-session.bst
- xfce-linux/xfconf.bst
- xfce-linux/garcon.bst
- xfce-linux/libxfce4windowing.bst
- xfce-linux/gtk-layer-shell.bst

sources:
- kind: git_repo
  url: xfce:xfce/xfdesktop.git
  track: xfdesktop-4.21.*
  ref: xfdesktop-4.21.1-0-g37729c473382ac6bd406b5e0742d7558060e7d43

# video-backdrop needs gstreamer's gtk sink (gst-plugin-gtk), which neither
# junction builds; meson stops with "gstreamer cannot find gst-plugin-gtk".
variables:
  meson-local: >-
    -Dwayland=enabled
    -Dvideo-backdrop=false
