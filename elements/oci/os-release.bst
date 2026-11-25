kind: manual
description: Brussels os-release configuration (pass-through element)

depends:
  - freedesktop-sdk.bst:public-stacks/runtime-minimal.bst

sources:
- kind: local
  path: files/etc/os-release

config:
  install-commands:
    - |
      mkdir -p "%{install-root}/usr/lib"
      cp os-release "%{install-root}/usr/lib/os-release"

variables:
  strip-binaries: ""



