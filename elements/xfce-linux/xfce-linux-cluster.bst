# XFCE Linux cluster — desktop environment built from upstream release tags
#
# Provides all core components and applications of the XFCE desktop environment
# built from official upstream release tags (tuna-os/xfce-linux#158).

kind: stack
description: |
  Complete XFCE desktop environment built from upstream release tags.
  Includes xfwl4 compositor, xfce4-panel, xfdesktop, thunar, xfce4-session,
  xfce4-settings, xfwm4, xfce4-terminal, xfce4-appfinder, xfce4-notifyd,
  xfce4-power-manager, tumbler, xarchiver, and all supporting libraries.

depends:
  # ── XFCE Desktop Environment Components (built from upstream release tags) ─
  - xfce-linux/libxfce4util.bst
  - xfce-linux/xfconf.bst
  - xfce-linux/libxfce4ui.bst
  - xfce-linux/garcon.bst
  - xfce-linux/libxfce4windowing.bst
  - xfce-linux/exo.bst
  - xfce-linux/xfwm4.bst
  - xfce-linux/xfce4-panel.bst
  - xfce-linux/xfce4-session.bst
  - xfce-linux/xfce4-settings.bst
  - xfce-linux/xfdesktop.bst
  - xfce-linux/thunar.bst
  - xfce-linux/tumbler.bst
  - xfce-linux/xfce4-appfinder.bst
  - xfce-linux/xfce4-terminal.bst
  - xfce-linux/xfce4-notifyd.bst
  - xfce-linux/xfce4-power-manager.bst
  - xfce-linux/xfwl4.bst

  # ── Supporting Applications & Config ───────────────────
  # xarchiver — GTK+ archive manager (xfce-linux#56)
  - xfce-linux/xarchiver.bst
  # XFCE default settings
  - xfce-linux/dconf-config.bst
  # XFCE users and config
  - xfce-linux/etc-config.bst

  # ── Core dependencies that everything needs ────────────
  - freedesktop-sdk.bst:public-stacks/runtime-minimal.bst
  - freedesktop-sdk.bst:components/gtk3.bst
  - gnome-build-meta.bst:sdk/gtk.bst
  - freedesktop-sdk.bst:components/glib.bst
  
  # Wayland
  - freedesktop-sdk.bst:components/wayland.bst
  - freedesktop-sdk.bst:components/wayland-protocols.bst
  - freedesktop-sdk.bst:components/pixman.bst
  - freedesktop-sdk.bst:components/libdrm.bst

  # System
  - freedesktop-sdk.bst:components/systemd.bst
  - freedesktop-sdk.bst:components/dbus.bst
  - freedesktop-sdk.bst:components/pipewire.bst
  - freedesktop-sdk.bst:components/alsa-lib.bst
  - xfce-linux/dbus-glib.bst

  # Libraries
  - freedesktop-sdk.bst:components/libnotify.bst
  - freedesktop-sdk.bst:components/polkit.bst
  - freedesktop-sdk.bst:components/libexif.bst
  - freedesktop-sdk.bst:components/libsoup.bst
  - freedesktop-sdk.bst:components/json-c.bst
  - freedesktop-sdk.bst:components/iso-codes.bst

  # gnome-build-meta deps
  - gnome-build-meta.bst:core-deps/vte.bst
  - gnome-build-meta.bst:core-deps/upower.bst
  - gnome-build-meta.bst:core-deps/libcanberra.bst
  - gnome-build-meta.bst:sdk/gtksourceview.bst

  # GStreamer
  - freedesktop-sdk.bst:components/gstreamer.bst
  - freedesktop-sdk.bst:components/gstreamer-plugins-base.bst
  - freedesktop-sdk.bst:components/gstreamer-plugins-good.bst

  # Python (for catfish, appfinder)
  - freedesktop-sdk.bst:components/python3.bst
