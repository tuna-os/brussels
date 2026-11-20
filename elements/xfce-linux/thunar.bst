kind: meson
description: |
  Modern file manager for the XFCE desktop environment (tuna-os/xfce-linux#158).

build-depends:
# meson.build: find_program('xsltproc', required: true)
- freedesktop-sdk.bst:components/libxslt.bst
# The man page is rendered with the DocBook manpages stylesheet, resolved
# offline through the XML catalog (xsltproc --nonet).
- freedesktop-sdk.bst:components/docbook-xsl.bst
- freedesktop-sdk.bst:public-stacks/buildsystem-meson.bst
- freedesktop-sdk.bst:components/gobject-introspection.bst
- freedesktop-sdk.bst:components/gettext.bst
- xfce-linux/xfce4-dev-tools.bst

depends:
- freedesktop-sdk.bst:public-stacks/runtime-minimal.bst
- freedesktop-sdk.bst:components/gtk3.bst
- freedesktop-sdk.bst:components/glib.bst
- freedesktop-sdk.bst:components/pango.bst
- freedesktop-sdk.bst:components/libnotify.bst
- freedesktop-sdk.bst:components/polkit.bst
- freedesktop-sdk.bst:components/systemd.bst
- freedesktop-sdk.bst:components/xorg-lib-x11.bst
- freedesktop-sdk.bst:components/xorg-lib-sm.bst
- freedesktop-sdk.bst:components/xorg-lib-ice.bst
- gnome-build-meta.bst:core-deps/libcanberra.bst
- gnome-build-meta.bst:core-deps/vte.bst
- xfce-linux/libxfce4util.bst
- xfce-linux/libxfce4ui.bst
- xfce-linux/xfconf.bst
- xfce-linux/exo.bst
- xfce-linux/xfce4-panel.bst

sources:
- kind: git_repo
  url: xfce:xfce/thunar.git
  track: thunar-*
  ref: thunar-4.21.6-0-ged1b159424b2e70339c6ccdeeea0a5cfbb9ae6b7
