# Brussels — TunaOS Xfce

[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](https://github.com/tuna-os/xfce-linux/blob/main/LICENSE)

**An experimental desktop with Xfce on Wayland, built with BuildStream.**
Brussels is part of [TunaOS](https://tunaos.org). It builds on GNOME OS,
freedesktop-sdk, Xfce, and xfwl4; ISO infrastructure follows
projectbluefin/dakota and dakota-iso. Credit belongs to those upstream projects.

The repository, BuildStream project identity, and published image remain
`tuna-os/xfce-linux` to preserve consumers and warm build caches.
The Brussels name recalls the Xfce Foundation launch:
FOSDEM in Brussels in 2011
([upstream announcement](https://blog.xfce.org/2011/02/xfce-foundation-e-v-launched-at-fosdem/)).

![Brussels by TunaOS wordmark](branding/brussels/xfce-linux-wordmark.svg)

Brussels artwork is original TunaOS work, not artwork from the Xfce Foundation.
This is not yet a qualified production distribution.
Runtime checks must demonstrate each candidate's boot and install behavior.

![Brussels desktop wallpaper preview](branding/brussels/brussels-wallpaper.png)

Icon: [Brussels product mark](branding/brussels/brussels-logo.svg).

<!-- hive-contribute-plea: donated-compute appeal, keep in sync across repos -->
## Contribute compute — no code needed

**[Donate time with your AI CLI](https://hub.tunaos.org/#contribute).**

Your machine runs one task at a time using your signed-in AI coding CLI.
The relay alternates between eligible **School** (OS) and **Reef** (apps)
hives after each task. If one hive has no work, the other can continue.

The guide covers prerequisites, verified `just` setup, credentials, provider
costs, and how to stop with Ctrl+C. Your subscription quota or API charges apply.
Never post account credentials or API keys in issues or pull requests.

## Features

- **Lightweight** — XFCE desktop optimized for low-resource systems
- **Immutable** — OCI-based, atomic updates via `bootc`
- **Wayland** — modern display protocol
- **BuildStream** — a pinned graph for the OS and desktop archive

The Xfce runtime now uses a pinned binary archive from
[hanthor/xfce-wayland](https://github.com/hanthor/xfce-wayland).
BuildStream builds the rest of the OS.
The complete desktop does not yet build from source in this project.

## Quick Start

```bash
# Pull the image
podman pull ghcr.io/tuna-os/xfce-linux:latest

# Switch an existing bootc system
sudo bootc switch ghcr.io/tuna-os/xfce-linux:latest
```

## Stable release channel

The release workflow publishes the first stable channel only after all checks
pass. The checks cover the nightly image, matching live ISO, plain install, and
LUKS install.
Release promotion also needs the approved key pair and exact image signature.
It retags the nightly digest after verification and does not build the OS again.

ISO, plain and LUKS evidence must identify that same commit and image digest.
Tests that use an old payload do not qualify a newer release.
The key pair and a policy for bootc signatures remain absent.
These prerequisites block stable/security qualification.

After promotion, select the stable channel:

```bash
podman pull ghcr.io/tuna-os/xfce-linux:stable
sudo bootc switch ghcr.io/tuna-os/xfce-linux:stable
```

The workflow publishes the stable live ISO and checksum under
`https://pub-<configured-r2-domain>/xfce-linux/stable/`. Their names are
`xfce-linux-live-latest.iso` and `xfce-linux-live-latest.iso-CHECKSUM`.
The promotion workflow verifies both objects before it marks the release as
ready. Thus, downstream download pages can safely use those stable names.

## Verifying Signatures

**OCI images:** SHA candidates have no signatures and do not qualify for security.
Release channels need the approved key pair, verified digest and a completed scan.
CI fails if the scanner or SARIF upload fails.
A build pass does not qualify an image with vulnerabilities.
Installed systems do not yet enforce signatures through bootc.
See [`docs/signing.md`](docs/signing.md) for the exact administrator prerequisites.

**Live ISO signatures:** each ISO has a Sigstore bundle (`.sigstore.json`).
The bundle contains its signature, certificate and transparency proof.
Use cosign 3 or newer:

```bash
ISO='xfce-linux-live-<date>-<sha>.iso'
digest=$(sha256sum -- "$ISO")
cosign verify-blob "sha256:${digest%% *}" \
  --bundle "${ISO}.sigstore.json" \
  --certificate-identity 'https://github.com/tuna-os/xfce-linux/.github/workflows/build-iso.yml@refs/heads/stable' \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com
```

This hashes the actual ISO as a stream.
Cosign checks that digest against the bundle and does not load the ISO into RAM.
For nightly or branch ISOs, use the exact ref from their workflow run instead of stable.

## Docs

- [XFCE Linux on tunaos.org](https://tunaos.org/docs/xfce-linux)
- [Local DDI with Mkosi (experimental)](docs/mkosi-ddi.md)
- [Contribution guide](CONTRIBUTING.md)

## License

Apache 2.0 — see [LICENSE](https://github.com/tuna-os/xfce-linux/blob/main/LICENSE).
