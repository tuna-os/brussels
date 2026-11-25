kind: autotools
description: dbus-glib - GLib bindings for D-Bus (required by xfce4-screensaver)

depends:
  - freedesktop-sdk.bst:public-stacks/runtime-minimal.bst
  - freedesktop-sdk.bst:components/glib.bst
  - freedesktop-sdk.bst:components/dbus.bst

build-depends:
  - freedesktop-sdk.bst:public-stacks/buildsystem-autotools.bst
  - freedesktop-sdk.bst:components/gettext.bst
  - freedesktop-sdk.bst:components/gobject-introspection.bst

sources:
- kind: tar
  url: dbus_releases:dbus-glib/dbus-glib-0.114.tar.gz
  ref: c09c5c085b2a0e391b8ee7d783a1d63fe444e96717cc1814d61b5e8fc2827a7c

# Use the project's configure arguments, not a bare `./configure --prefix=/usr`.
# A bare configure installs to /usr/lib, and pkg-config in this SDK reads
# %{libdir} (/usr/lib/<multiarch>), so xfce4-screensaver could not find
# dbus-glib-1.pc. The dynamic loader does not read /usr/lib for it either.
variables:
  conf-local: >-
    --disable-gtk-doc
    --disable-static
    --enable-shared
