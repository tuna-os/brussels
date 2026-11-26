kind: junction

sources:
- kind: git_repo
  url: gnome:gnome-build-meta.git
  track: gnome-50
  ref: 50.4-0-g8524013485013dd5616bfff02dbeab274d5a4553
- kind: patch_queue
  # GNOME's secure-boot elements refer to generated key paths that do not
  # exist in a clean source checkout. Keep the existing generated-source
  # support, but drop the unrelated local patches so more keys align.
  path: patches/gnome-build-meta

config:
  overrides:
    # This along with the patches is required and has to match what gnome-build-meta is using
    freedesktop-sdk.bst: freedesktop-sdk.bst

    # One libdisplay-info. gnome-build-meta has 0.4.0 for mutter, and the XFCE
    # elements use 0.3.0 from freedesktop-sdk: both in one tree is an overlap
    # error. xfwl4 locks libdisplay-info-sys 0.3.0, which refuses 0.4. mutter
    # takes 0.2 or newer. Drop this when xfwl4 accepts 0.4.
    core-deps/libdisplay-info.bst: freedesktop-sdk.bst:components/libdisplay-info.bst

    # Replace the element so the OCI image has XFCE instead of GNOME apps
    core/meta-gnome-core-apps.bst: core/meta-xfce-core-apps.bst

    # TODO: os-release is handled by gnome-build-meta; skip custom override for now
    # oci/integration/os-release.bst: oci/os-release.bst

    plugins/buildstream-plugins.bst: plugins/buildstream-plugins.bst
    plugins/buildstream-plugins-community.bst: plugins/buildstream-plugins-community.bst
