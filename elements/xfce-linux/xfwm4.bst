kind: autotools
description: |
  XFCE window manager and window themes (tuna-os/xfce-linux#158).
  Provides xfwm4 window themes required by the xfwl4 compositor.

build-depends:
- freedesktop-sdk.bst:public-stacks/buildsystem-autotools.bst
- freedesktop-sdk.bst:components/gettext.bst
- xfce-linux/intltool.bst
- xfce-linux/xfce4-dev-tools.bst

depends:
- freedesktop-sdk.bst:public-stacks/runtime-minimal.bst
- freedesktop-sdk.bst:components/gtk3.bst
- freedesktop-sdk.bst:components/glib.bst
- freedesktop-sdk.bst:components/libepoxy.bst
- freedesktop-sdk.bst:components/xorg-lib-x11.bst
- freedesktop-sdk.bst:components/xorg-lib-xinerama.bst
- freedesktop-sdk.bst:components/xorg-lib-xrandr.bst
- freedesktop-sdk.bst:components/xorg-lib-xcomposite.bst
- freedesktop-sdk.bst:components/xorg-lib-xdamage.bst
- freedesktop-sdk.bst:components/xorg-lib-xfixes.bst
- freedesktop-sdk.bst:components/xorg-lib-xrender.bst
- freedesktop-sdk.bst:components/xorg-lib-xi.bst
- freedesktop-sdk.bst:components/xorg-lib-xext.bst
- xfce-linux/libxfce4util.bst
- xfce-linux/libxfce4ui.bst
- xfce-linux/xfconf.bst
- xfce-linux/libwnck.bst

sources:
# Release tarball, not the git tag: autogen.sh turns on maintainer mode,
# where the settings dialogs' *_ui.h headers must be regenerated and the
# build failed with "xfwm4-dialog_ui.h: No such file or directory". The
# tarball ships configure and the generated headers.
- kind: tar
  url: xfce_archive:src/xfce/xfwm4/4.20/xfwm4-4.20.0.tar.bz2
  ref: a58b63e49397aa0d8d1dcf0636be93c8bb5926779aef5165e0852890190dcf06

variables:
  # settings-dialogs/Makefile.am links xfwm4-settings and
  # xfwm4-tweaks-settings without LIBXFCE4UTIL_LIBS while calling
  # xfce_textdomain() and xfce_resource_push_path() directly. GNU ld
  # rejects the indirect dependency ("DSO missing from command line").
  conf-local: LIBS=-lxfce4util

# xfwl4 needs xfwm4 for two things only (xfwl4 README, "Prerequisites"):
# its window themes (xfwl4 will not start without them) and its settings
# dialogs (xfwm4-settings, xfwm4-tweaks-settings), which write the xfwm4
# xfconf channel that xfwl4 reads. The X11 window manager binary itself is
# never started on this Wayland-only image, so it is not shipped.
config:
  install-commands:
    (>):
    - rm -f "%{install-root}%{bindir}/xfwm4"
