# XFCE Linux — Agent Context

XFCE Linux is a BuildStream-based, vanilla-from-source XFCE (Wayland, xfwl4)
OCI/bootc image. Sister project of `tuna-os/tromso` (KDE + Aurora layer);
both are modeled on projectbluefin/dakota + dakota-iso. An opinionated
experience layer on top (like tromso's Aurora layer) is planned but not yet
started.

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
- Plymouth: the gnomeos parent already ships plymouth + GNOME watermark;
  `elements/xfce-linux/plymouth-theme.bst` shadows it (XFCE logo) and must
  keep its `runtime-depends` on the GNOME theme to win the staging order.
- Renovate handles Actions/containers; `.bst` refs are bumped by
  `track-bst-sources.yml` (`bst source track`). Junction bumps
  (freedesktop-sdk, gnome-build-meta) are review-required.
- Committed binary trees and large generated filemaps (issues #16/#17/#158)
  were dropped from git in the repo-hygiene cleanup:
  `elements/xfce-linux/` now builds all XFCE desktop components directly
  from upstream release tags (#158), retiring `xfce-binaries.bst` and the
  `xfce-wayland` fork. `files/filemap.json` + `files/fakecap-manifest.tsv` are
  generated at build time by `scripts/gen-filemap.py`. Don't re-commit them.
  `xfwl4-headers/` was removed in the #15 cleanup — vendored
  build-only headers that were never referenced by any .bst element.

## CI gate rules (hard-won)

- Never add `paths:` filters to workflows whose jobs are required checks —
  a non-reporting required check deadlocks automerge (test.yml filters were
  removed for exactly this).
- Renaming a required job means updating the branch-protection contexts in
  the same PR.
- Never wrap a gate in `|| echo` — that's how checks go silently dead.
- `tests/pytest/test_iso_invariants.py` encodes shipped bug classes; when
  you fix a CI/ISO bug, add an invariant there and a row to
  docs/ci-and-iso-pipeline.md.
