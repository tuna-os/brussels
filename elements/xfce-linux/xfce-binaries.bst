kind: import
description: >-
  Pre-built XFCE binaries from the hanthor/xfce-wayland monorepo.

  The binary tree was previously committed to git (issue #16) and is now
  fetched from the last commit that carried it. The extracted tree stays
  gitignored (files/xfce-binaries/) — do not re-commit it.

sources:
- kind: tar
  url: https://github.com/tuna-os/xfce-linux/archive/1351dffdda05b4ffab35d26a97b26c51d5841742.tar.gz
  ref: 6ba2e200dd19faf5e1e8ccde62e58615cdb05312a65e519d6ffc60376dc4de3a
  base-dir: xfce-linux-1351dffdda05b4ffab35d26a97b26c51d5841742/files/xfce-binaries/install
