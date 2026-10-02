kind: meson
description: |
  libwnck-3.0, the window-navigator library xfwm4 requires
  (XDT_CHECK_PACKAGE([LIBWNCK], [libwnck-3.0]) in its configure.ac).
  Neither gnome-build-meta (gnome-50) nor freedesktop-sdk 25.08 ships it.
  Built without GObject introspection, startup-notification (not in either
  junction; optional) and the wnck tools, which nothing here uses.

build-depends:
- freedesktop-sdk.bst:public-stacks/buildsystem-meson.bst
- freedesktop-sdk.bst:components/gettext.bst

depends:
- freedesktop-sdk.bst:public-stacks/runtime-minimal.bst
- freedesktop-sdk.bst:components/gtk3.bst
- freedesktop-sdk.bst:components/glib.bst
- freedesktop-sdk.bst:components/xorg-lib-x11.bst
- freedesktop-sdk.bst:components/xorg-lib-xi.bst

sources:
- kind: tar
  url: gnome_downloads:libwnck/43/libwnck-43.3.tar.xz
  ref: 6af8ac41a8f067ade1d3caaed254a83423b5f61ad3f7a460fcacbac2e192bdf7

variables:
  meson-local: >-
    -Dintrospection=disabled
    -Dstartup_notification=disabled
    -Dinstall_tools=false
    -Dgtk_doc=false
