# Brussels — Agent Context

Brussels is TunaOS's experimental BuildStream-based Xfce Wayland (xfwl4)
OCI/bootc image. The repository, BuildStream project and image remain
`xfce-linux` to preserve consumers and caches. Sister projects are Athens
(Pantheon) and Tromsø (KDE). Upstream GNOME OS, freedesktop-sdk, Xfce and
projectbluefin/dakota infrastructure retain their credit.

## Architecture

- **Base**: gnome-build-meta's gnomeos OCI image (junction `gnome-build-meta.bst`,
  branch gnome-50) — provides freedesktop-sdk, systemd, kernel, bootc,
  plymouth, GDM.
- **XFCE layer**: `elements/xfce-linux/` (xfconf, libxfce4*, xfwl4 compositor,
  session config) composed in `elements/oci/layers/`, final target
  `oci/xfce-linux.bst` → `ghcr.io/tuna-os/xfce-linux`.
- **Live ISO**: `xfce-linux/` directory (Containerfile + src/) + `iso.justfile`
  recipes. See `docs/ci-and-iso-pipeline.md` for the full chain and the
  CI troubleshooting log.

## Reference repos are authoritative

Never invent workarounds for build issues. For infrastructure, bootc,
systemd, initramfs, OCI composition: copy patterns from
gnome-build-meta (gitlab.gnome.org/GNOME/gnome-build-meta, branch gnome-50)
and projectbluefin/dakota. For XFCE package specifics: Arch PKGBUILDs and
gitlab.xfce.org upstream.

## Commands

```bash
just bst build oci/xfce-linux.bst   # full image build (bst2 container)
just export && just lint            # OCI export + bootc container lint
just iso-sd-boot xfce-linux         # live ISO (sudo; needs podman/buildah/xorriso/mtools)
just debug=1 iso-sd-boot xfce-linux # ISO with SSH enabled (liveuser/live)
just boot-iso-vnc xfce-linux        # boot ISO, VNC on :10, serial telnet 4445
just luks-test-qemu xfce-linux      # full LUKS install e2e (needs built ISO)
```

Heavy builds should run in CI, not on a laptop.

## Gotchas (hard-won; don't reintroduce)

- `Justfile` is the single just entry point; ISO recipes live in
  `iso.justfile` via `import`. Never create a second root justfile —
  just ≥1.30 hard-errors on ambiguity and all CI dies.
- The installer frontend is `org.tunaos.InstallerXfce` from the tuna-os OCI
  flatpak remote (`https://tunaos.org/flatpak/tuna-os.flatpakrepo`), baked
  into the ISO only — never into the OS image. Keep
  `install-flatpaks.sh` and `configure-live.sh` referring to the *same* app ID.
- Plymouth: GNOME OS supplies the bgrt/spinner theme.
  `elements/xfce-linux/plymouth-theme.bst` installs original Brussels artwork;
  retain its runtime dependency on the GNOME theme for staging order.
- Live media embeds `/usr/lib/tunaos/payload` as a read-only OCI layout.
  `scripts/embed-payload.sh` records the actual platform manifest/config in
  `/etc/bootc-installer/media-input.json`; fisherman must verify it before
  partitioning. Never reintroduce VFS/network fallback or omit this contract.
- Live and embedded payloads resolve from one immutable registry digest.
- ISO signing uses a Sigstore `.sigstore.json` bundle (cosign 3+), not the
  deprecated detached `.sig`/`.cert` flags.
- Renovate handles Actions/containers; `.bst` refs are bumped by
  `track-bst-sources.yml` (`bst source track`). Junction bumps
  (freedesktop-sdk, gnome-build-meta) are review-required.
- Committed binary trees and large generated filemaps (issues #16/#17)
  were dropped from git in the repo-hygiene cleanup:
  `files/xfce-binaries/` is now fetched by `xfce-binaries.bst` from a
  pinned tarball, and `files/filemap.json` +
  `files/fakecap-manifest.tsv` are generated at build time by
  `scripts/gen-filemap.py`. Don't re-commit any of them.
  `xfwl4-headers/` was removed in the #15 cleanup — vendored
  build-only headers that were never referenced by any .bst element.

## CI gate rules (hard-won)

- Never add `paths:` filters to workflows whose jobs are required checks —
  a non-reporting required check deadlocks automerge (test.yml filters were
  removed for exactly this).
- Renaming a required job means updating the branch-protection contexts in
  the same PR.
- Never wrap a gate in `|| echo` — that's how checks go silently dead.
- For CI/ISO fixes, add a consumer-visible behavior regression where practical,
  or record real runtime smoke evidence. Do not add source-text/wiring assertions.
  Update the troubleshooting record in docs/ci-and-iso-pipeline.md.
