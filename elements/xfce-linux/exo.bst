kind: autotools
description: |
  Application library for the XFCE desktop environment (tuna-os/xfce-linux#158).

build-depends:
- freedesktop-sdk.bst:public-stacks/buildsystem-autotools.bst
- freedesktop-sdk.bst:components/gettext.bst
- xfce-linux/intltool.bst
- xfce-linux/xfce4-dev-tools.bst

depends:
- freedesktop-sdk.bst:public-stacks/runtime-minimal.bst
- freedesktop-sdk.bst:components/gtk3.bst
- freedesktop-sdk.bst:components/glib.bst
- xfce-linux/libxfce4util.bst
- xfce-linux/libxfce4ui.bst

sources:
# Release tarball, not the git tag: from git, xdt-autogen refuses to run
# without gtk-doc installed ("You must have gtk-doc installed"), which no
# junction element here provides. The tarball ships configure.
- kind: tar
  url: xfce_archive:src/xfce/exo/4.21/exo-4.21.0.tar.bz2
  ref: 26f85ca2db3bcf99d8b8af28b0d565b0186ccc3d2ed4a5ba315f6a589b8bc2c9

variables:
  conf-local: --disable-gtk-doc
