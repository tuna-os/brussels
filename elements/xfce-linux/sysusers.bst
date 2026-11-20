kind: manual
description: Install XFCE system users and tmpfiles.

depends:
  - freedesktop-sdk.bst:public-stacks/runtime-minimal.bst

sources:
- kind: local
  path: files/etc/sysusers.d
  directory: sysusers.d
- kind: local
  path: files/etc/tmpfiles.d
  directory: tmpfiles.d

config:
  install-commands:
    - |
      mkdir -p "%{install-root}/usr/lib/sysusers.d"
      cp sysusers.d/xfce-user.conf "%{install-root}/usr/lib/sysusers.d/"
      mkdir -p "%{install-root}/usr/lib/tmpfiles.d"
      cp tmpfiles.d/xfce-home.conf "%{install-root}/usr/lib/tmpfiles.d/"

variables:
  strip-binaries: ""

