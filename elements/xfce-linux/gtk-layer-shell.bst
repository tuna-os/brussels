kind: meson
description: |
  gtk-layer-shell — GTK3 library for the wlr-layer-shell Wayland protocol.

  Neither junction ships it. On Wayland, xfce4-panel, xfdesktop,
  xfce4-notifyd, xfce4-session (logout dialog), xfce4-settings and the
  xfce4-terminal drop-down need it to place their surfaces; without it the
  panel and desktop open as ordinary toplevel windows. Every XFCE 4.21
  meson.build asks for gtk-layer-shell-0 >= 0.7.0.

build-depends:
- freedesktop-sdk.bst:public-stacks/buildsystem-meson.bst
- freedesktop-sdk.bst:components/wayland-protocols.bst

depends:
- freedesktop-sdk.bst:public-stacks/runtime-minimal.bst
- freedesktop-sdk.bst:components/gtk3.bst
- freedesktop-sdk.bst:components/wayland.bst

sources:
- kind: git_repo
  url: github:wmww/gtk-layer-shell.git
  track: v*
  ref: v0.10.1-0-gfd88ba666c18ff65ea786bf7b2e270d840030817

# No consumer uses the GObject introspection data or the Vala bindings.
variables:
  meson-local: >-
    -Dintrospection=false
    -Dvapi=false
    -Dexamples=false
    -Dtests=false
    -Ddocs=false
