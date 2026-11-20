kind: autotools
description: |
  XFCE development tools (xdt-autogen, macros, and visibility tools).
  Build toolchain for XFCE autotools and meson elements (tuna-os/xfce-linux#158).

build-depends:
- freedesktop-sdk.bst:public-stacks/buildsystem-autotools.bst
- freedesktop-sdk.bst:components/glib.bst
# configure hard-requires xsltproc to build the xdt-csource man page.
- freedesktop-sdk.bst:components/libxslt.bst
# ...and meson on PATH (it checks for the program, not a library).
- freedesktop-sdk.bst:public-stacks/buildsystem-meson.bst

depends:
- freedesktop-sdk.bst:public-stacks/runtime-minimal.bst
- freedesktop-sdk.bst:components/glib.bst

sources:
# The release tarball, not the git tag: git lacks the generated
# docs/xdt-csource.1, which is only rebuilt in maintainer mode (and then
# needs the DocBook stylesheets from the network), so `make` stopped with
# "No rule to make target 'xdt-csource.1'". The tarball also ships
# configure, so autogen.sh is not needed.
- kind: tar
  url: xfce_archive:src/xfce/xfce4-dev-tools/4.21/xfce4-dev-tools-4.21.2.tar.bz2
  ref: a43f726a082b589186d9e6ed076101d41249d1e22bbe61448037550190d7f75a
