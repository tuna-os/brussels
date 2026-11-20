kind: compose
description: |
  The files that turn the xfce-linux image into brussels-winblues. Only
  this tree is built here: variants/winblues/Containerfile lays it over the
  exported xfce-linux image, so the variant reuses every base layer and
  costs one small layer (docs/winblues.md).

  The elements have no runtime dependencies, so the compose holds their
  own files and nothing from the base image.

build-depends:
- winblues/chicago95.bst
- winblues/config.bst
