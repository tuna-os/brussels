kind: manual
description: >-
  Original Brussels product artwork by TunaOS: icon, wordmark, and wallpaper
  asset. It does not use the official Xfce logo.

sources:
- kind: local
  path: branding/brussels

depends:
- gnome-build-meta.bst:freedesktop-sdk.bst:public-stacks/runtime-minimal.bst

config:
  install-commands:
  - install -Dm644 brussels-logo.svg '%{install-root}%{datadir}/icons/hicolor/scalable/apps/brussels-logo.svg'
  - install -Dm644 xfce-linux-wordmark.svg '%{install-root}%{datadir}/tunaos/branding/xfce-linux-wordmark.svg'
  - install -Dm644 brussels-wallpaper.svg '%{install-root}%{datadir}/tunaos/branding/brussels-wallpaper.svg'
  - install -Dm644 brussels-wallpaper.png '%{install-root}%{datadir}/backgrounds/TunaOS/Brussels/brussels-wallpaper.png'
  - '%{install-extra}'

variables:
  strip-binaries: ''
