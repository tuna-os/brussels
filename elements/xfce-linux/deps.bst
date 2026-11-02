# XFCE Linux dependencies stack
#
# Pulls in freedesktop-sdk base plus all dependencies needed for the
# XFCE desktop stack, xfwl4 compositor, and supporting applications.

kind: stack
description: |
  XFCE Linux desktop stack dependencies and applications.

depends:
  # gnome-build-meta base (provides freedesktop-sdk infrastructure)
  - gnome-build-meta.bst:gnomeos-deps/deps.bst

  # ── XFCE Desktop Stack (from our monorepo) ─────────────
  - xfce-linux/xfce-linux-cluster.bst

  # ── XFCE Opinionated Experience Layer (Aurora equivalent, xfce-linux#40) ─
  - xfce-linux/experience-layer.bst

  # ── XFCE Session Configuration & Branding ──────────────
  - xfce-linux/session-config.bst
  # Brussels splash shadows the parent layer's GNOME watermark.
  - xfce-linux/plymouth-theme.bst
  - xfce-linux/branding.bst

  # ── freedesktop-sdk utilities ──────────────────────────
  - freedesktop-sdk.bst:components/buildstream2.bst
  - freedesktop-sdk.bst:components/debuginfod.bst
  - freedesktop-sdk.bst:components/git.bst
  - freedesktop-sdk.bst:components/git-lfs.bst
  - freedesktop-sdk.bst:components/podman.bst
  - freedesktop-sdk.bst:components/skopeo.bst
  - freedesktop-sdk.bst:components/containers-common.bst

  # ── System tools ───────────────────────────────────────
  - freedesktop-sdk.bst:components/bpf.bst
  - freedesktop-sdk.bst:components/vmlinuxh.bst
  - gnome-build-meta.bst:gnomeos-deps/just.bst
  - gnome-build-meta.bst:gnomeos-deps/wl-clipboard.bst
  - freedesktop-sdk.bst:components/libseat.bst
  - freedesktop-sdk.bst:components/libdisplay-info.bst
