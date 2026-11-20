kind: meson
description: |
  xfce4-screensaver — the XFCE screen saver and screen locker.

  Built with its Wayland backend only. On Wayland it locks the session
  through the ext-session-lock-v1 protocol, which xfwl4 implements
  (xfwl4 4.21.1 NEWS: "Fix various issues with the ext-session-lock-v1
  protocol impl"). Upstream ships the Wayland backend disabled by default,
  so treat it as experimental. See docs/session-and-locking.md.

build-depends:
- freedesktop-sdk.bst:public-stacks/buildsystem-meson.bst
- freedesktop-sdk.bst:components/gettext.bst
- freedesktop-sdk.bst:components/wayland-protocols.bst
- xfce-linux/xfce4-dev-tools.bst

depends:
- freedesktop-sdk.bst:public-stacks/runtime-minimal.bst
- freedesktop-sdk.bst:components/gtk3.bst
- freedesktop-sdk.bst:components/glib.bst
- freedesktop-sdk.bst:components/dbus.bst
- freedesktop-sdk.bst:components/wayland.bst
- freedesktop-sdk.bst:components/linux-pam.bst
- freedesktop-sdk.bst:components/systemd.bst
- xfce-linux/dbus-glib.bst
- xfce-linux/libxfce4util.bst
- xfce-linux/libxfce4ui.bst
- xfce-linux/xfconf.bst
- xfce-linux/garcon.bst
- xfce-linux/libxfce4windowing.bst
- xfce-linux/libwlembed.bst

sources:
- kind: git_repo
  url: xfce:apps/xfce4-screensaver.git
  track: xfce4-screensaver-*
  ref: xfce4-screensaver-4.20.2-0-g688218e95af75b6af740f42bb2402948f13ecfdd

# Wayland only: the X11 backend needs libXScrnSaver and libxklavier, and
# this image has no X11 session.
variables:
  meson-local: >-
    -Dwayland=enabled
    -Dx11=disabled
    -Dauthentication-scheme=pam
    -Dpam-auth-type=system
    -Dsession-manager=systemd
    -Ddocs=disabled
