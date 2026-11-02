# CI & ISO pipeline

How xfce-linux gets from `.bst` elements to a bootable, installable live ISO —
and how to debug it when it breaks. (Same architecture as tuna-os/xfce-linux;
patterns originate in projectbluefin/dakota and dakota-iso.)

## Build chain

```
elements/**  ──►  Build xfce-linux (Multi-Runner)  ──►  ghcr.io/tuna-os/xfce-linux:latest
                        │ (workflow_run)
                        ▼
              Build and Publish xfce-linux Live ISO  ──►  R2: xfce-linux/xfce-linux-live-*.iso
                        │
                        ▼ (boot gate: XFCE_LINUX_LIVE_READY on serial + screenshot)
              LUKS Install End-to-End Test (PR round-robin / weekly / dispatch)
```

### Multi-runner build (`build-multirunner.yml`)

The plan, core, and parallel dependency chunks (steps 1-3) use the shared
[tuna-os/bst-ci](https://github.com/tuna-os/bst-ci) reusable workflow. Each
BuildStream desktop repository uses this workflow, with different image names,
targets, and chunk counts. The local `build_final` job (step 4) publishes a SHA
candidate. Release channels need the approved key pair and a completed scan.
The ISO uses GitHub OIDC with a Sigstore bundle.

Free GitHub runners can't hold the whole GNOME+XFCE build, so the workflow
splits it:

1. **plan** — The `scripts/ci-build-matrix.py` script from bst-ci runs
   `bst show`. It splits uncached elements into a core set (first `CORE_SPLIT`)
   and `NUM_CHUNKS` round-robin chunks. Each chunk has a composite cache key.
   The job checks out the script from bst-ci at run time. This repository no
   longer contains a copy.
2. **build_core** — builds the bootstrap set, pushes the CAS as
   `ghcr.io/…/cache-xfce-linux-core:latest` (zstd tarball via oras).
3. **build_deps** (matrix) — each chunk restores core + its own previous CAS,
   builds, and pushes `cache-xfce-linux-<chunk>:{latest,<cache-key>}`. The job
   skips a chunk when GHCR already has its exact cache key.
4. **build_final** — merges the CAS archives and builds the final target.
   It runs `just export` (squash + OCI labels + chunkify) and `just lint`.
   It captures the registry digest with `podman push --digestfile`.
   Every candidate must pass the scanner and SARIF upload.
   Main and stable sign and verify that digest before they update channel tags.
   Branch builds publish experimental candidates without signatures.

BuildStream settings CI uses live in the checked-in `buildstream-ci.conf`.

**Cache-key invalidation warning:** a change to the cache key of every element
causes a full world rebuild. A change to `name:` in `project.conf` is one
example. Expect chunk jobs to run for hours or reach their six-hour limit once.
They recover after they refresh the GHCR caches.

### Live ISO (`iso.justfile` + `xfce-linux/`)

`just iso-sd-boot xfce-linux` (see `iso.justfile`, imported from `Justfile`):

1. `just container xfce-linux` — 3-stage `xfce-linux/Containerfile`:
   ghcr payload (kernel modules) → Debian stage builds a dmsquash-live
   initramfs (incl. the `95xfce-linux-isofile` Ventoy dracut module) → final
   stage installs flatpaks (`src/install-flatpaks.sh`) and configures the
   live env (`src/configure-live.sh`).
2. Resolve the payload once to its immutable registry digest.
   Combine the canonical name from the registry with its digest. Do not include a tag.
   Skopeo rejects a reference that combines a tag and digest.
   `scripts/prepare-payload.sh` prepares a source image before live-only changes.
   It injects the root-mount policy and squashes all layers for composefs.
   It records the actual layer diffid as an OCI label and annotation.
   Both use the name `ostree.final-diffid`, as in dakota-iso's payload helper.
   The cache key includes the source digest and preparation version.
   A cache hit avoids another pull or squash.
   The live container and install payload use the same prepared source.
   `scripts/embed-payload.sh` copies it from container storage to an OCI layout at
   `/usr/lib/tunaos/payload`. Its actual manifest/config digests populate
   `/etc/bootc-installer/media-input.json`.
   Fisherman verifies this contract before it partitions the disk.
   The media does not advertise a VFS store or network fallback.
   Both GUI catalogs track the same media image.
3. `xfce-linux/src/build-iso.sh` assembles a systemd-boot UEFI ISO.

The live session automatically logs in to XFCE on Wayland through xfwl4 as
`liveuser`. It starts `org.tunaos.InstallerXfce` from the OCI flatpak remote
for tuna-os. A symbolic link at `/usr/local/bin/fisherman` points to fisherman.
It uses the shared `org.tunaos.Installer.install` polkit action. See
INSTALLER-FRONTENDS.md in the organization workspace.

### LUKS end-to-end test (`test-luks-install.yml`)

Local equivalent:

```bash
just debug=1 iso-sd-boot xfce-linux     # debug=1 enables SSH (liveuser/live)
just luks-test-qemu xfce-linux          # boot → fisherman LUKS install → reboot → unlock
```

`xfce-linux/src/luks-unlock.py` drives the QEMU monitor. It checks screen dumps
until Plymouth appears, types the passphrase with `sendkey`, and verifies the
installed system boot. The workflow publishes screenshots to the
`ci-screenshots` branch and PR comments. They show the live desktop, Plymouth
prompt, and installed desktop.

## Source updates

- **Renovate** (`renovate.json`) — GitHub Actions, container tags. Automerge
  on green CI, majors included.
- **`track-bst-sources.yml`** — Renovate can't parse `.bst`; this runs
  `bst source track` daily. Local elements (`elements/xfce-linux`,
  `elements/core`) go into one automergeable PR; the
  `freedesktop-sdk.bst` + `gnome-build-meta.bst` junctions get a separate review-required PR (a
  junction bump can rebuild the world). PRs made with the default
  `GITHUB_TOKEN` don't trigger CI — set a `BOT_TOKEN` secret to fix that.

## Troubleshooting log (symptom → root cause → fix)

| Date | Symptom | Root cause | Fix |
|---|---|---|---|
| 2026-10-25 | Failed Multi-Runner runs immediately launch failing Live ISO builds (#131) | `workflow_run: completed` includes failed and cancelled builds | Require a successful upstream conclusion at the ISO job boundary; push and manual triggers remain available. This suppresses failure cascades; it does not verify image publication or gate independent install E2E runs. |
| 2026-07-19 | Every `just` call in CI fails: "multiple candidate justfiles" | `justfile` + `Justfile` both at root; just ≥1.30 hard-errors | ISO recipes moved to `iso.justfile`, imported from `Justfile` |
| 2026-07-19 | All 10 chunk jobs building for 5+ h | `project.conf` `name:` (tromso example) renaming project changes every cache key → world rebuild | expected one-time cost; caches repopulate |
| 2026-07-19 | Installer flatpak never launched in live session | install-flatpaks.sh baked `org.bootcinstaller.Installer` while configure-live.sh wired `org.xfceinstaller.Installer` | both sides now use `org.tunaos.InstallerXfce` |

| 2026-07-19 | Multi-runner never went green since May; every run "cancelled" at ~6.5 h | chunk jobs killed by job-level `timeout-minutes` — a cancelled job never reaches the CAS-push step, so 6 h × 10 chunks of build work was discarded daily (≈720 runner-hours; zero chunk cache packages ever existed on GHCR) | build bounded *inside* the step (`timeout 270m`), push steps `if: always()` — partial CAS salvaged, builds converge across days |
| 2026-07-19 | Failed chunks could publish their exact-cache-key tag and be skipped forever | `for i in 1 2 3 … done` retry loop exits 0 on total failure (status of last `sleep`) | retry loop removed (bst retry-failed/network-retries already cover it); rc propagated |

| 2026-07-19 | LUKS e2e / ISO jobs die in seconds: "Unknown attribute `group`" at Justfile:5 | Ubuntu 24.04 apt ships just 1.21 (predates `[group()]`); old runs survived because ancient just silently picked the group-free lowercase justfile we removed | workflows install just via extractions/setup-just and invoke `sudo "$(command -v just)"` |
| 2026-07-21 | Superseded push checks and image/ISO builds remained queued for hours | high-frequency workflows lacked concurrency groups or explicitly queued stale same-ref work | same-ref concurrency groups cancel superseded image publishes; Test and automatic ISO builds now preserve every run (see #140 below) |
| 2026-10-25 | Merged commits retain cancelled required checks (#140); ISO triggers can also evict each other | Ref-based concurrency groups cancel running work and replace pending work during merge trains | Test uses PR numbers only for PRs and unique run IDs otherwise; ISO uses unique run IDs for automatic triggers and branch groups only for manual reruns. Event-scoped cancellation preserves automatic verdicts; `test_automatic_checks_and_iso_builds_preserve_every_run` guards both policies |
| 2026-09-10 | `build_final` dies with no job log and no uploaded build log; `:latest` last published ~2026-07-19, so every LUKS/Plain E2E run fails with `manifest unknown` | Runner disk exhaustion, not a build error: the check-run annotation on runs 34072176433, 34176106533 and 34298830711 is the runner agent's own `System.IO.IOException: No space left on device` on its `_diag` log. Core plus ten chunk CAS tarballs measured ~266 GB compressed on 2026-09-10 (chunks 20-29 GB each) against ~100-110 GB of runner disk, because each chunk tarball embeds a full copy of core, nothing expires (no `cache.quota`), and `oras pull -o .` staged each tarball on disk before extracting. Run 34298830711 is decisive: the build itself succeeded in 18 min and the runner died in `Export OCI image` | Stream restores via `scripts/cas-restore-stream.sh` (`oras blob fetch --output -`); `cache: quota: 60G` in `buildstream-ci.conf`; check the artifact out and delete the CAS before `just export` (`EXPORT_REUSE_CHECKOUT=1`); log `df -h /` around every merge. Invariants in `tests/pytest/test_ci_disk_invariants.py` |

Add rows to this table as you change CI. See the organization `ci-fix-loop`
skill. The `docs/ci-troubleshooting.md` file in tuna-os/tunaos shows the format.

## Channels: nightly (main) and stable

- **main** is the nightly trunk: the daily scheduled multi-runner build
  publishes `:latest`, `:nightly`, `:nightly-YYYYMMDD`, `:<sha>`; the ISO
  lands at R2 `xfce-linux/`.
- **stable** is a release bookmark branch. A weekly schedule or manual dispatch
  starts `promote-stable.yml`. The approved key pair is mandatory, with no
  force bypass. The newest main build, ISO, plain and LUKS health runs must
  match one commit. ISO, plain and LUKS runs record the
  digest of the pinned payload, image revision and workflow commit as qualification artifacts.
  All three must match that SHA image, not an older test payload.
  The workflow verifies that SHA image's signature, advances
  the stable branch and retags the **same digest**. It does not build the OS again.
  It dispatches only the stable ISO with that verified immutable payload.
  The workflow verifies the stable digest, ISO checksum and OIDC bundle.
- Update PRs from source trackers or Renovate target only main. Stable moves
  only through promotion.

## Release-linked sources

Local elements use upstream **release tags** (globs such as `v[0-9]*`) instead
of development branches. Thus, the daily `bst source track` selects releases.
Some content repositories use branches, such as aurora common, docs,
wallpapers, and the xfwl4 development repositories. Junctions also use a fixed
branch. Do not set `track:` to one exact tag, because the tracker cannot move it.

## Guard rails (what stops a bad commit)

Branch protection needs the pre-merge checks on main. Automerge starts when
they pass. The checks include shellcheck, yamllint, actionlint, BATS, and pytest.
They also include the 52-test luks-unlock suite and `test_iso_invariants.py`.
Each invariant represents a defect that reached users.

The BuildStream graph gate runs `bst show --deps all` on the release target and
resolves junctions. `Just Parse` is also a check. `pr-build-changed.yml`
builds the elements that a PR changes against the core CAS from GHCR. It is
not a required check, and it runs only when a PR changes a `.bst` element.

Post-merge: salvage-enabled nightly world build → ISO boot gate
(ready-marker + screenshot artifact) → weekly LUKS install e2e
(screenshots on the `ci-screenshots` branch + PR comments). A cloud
routine ("tromso + xfce-linux CI babysitter", every 3 h) diagnoses
completed failures from logs and pushes fixes.

**Rules that keep this healthy:** do not add `paths:` filters to workflows with
required jobs. An absent required check prevents automerge. If you rename a
required job, update the branch protection contexts in the same PR. Do not wrap
a gate in `|| echo`. Such a wrapper hid failures in bst-validate and pytest for
months.

### Pull request CI (`test.yml`)

All pre-merge checks are in one workflow, `test.yml`. Its `changes` job lists
the changed files and starts only the jobs that those files can affect. A
skipped job reports success, so each required check always reports. If the
`changes` job fails, all checks run. A change to `test.yml` runs all checks.

| Job | Runs when the change touches |
|-----|------------------------------|
| shellcheck | `*.sh`, `*.bash` |
| yamllint | `*.yml`, `*.yaml` |
| actionlint | `.github/workflows/`, `.github/actions/` |
| Renovate Config Validate | `renovate.json` |
| lint .bst files | `*.bst` |
| BuildStream Graph | a file outside docs, tests, scripts, tools, `xfce-linux/`, `.github/` and the justfiles |
| Unit Tests | a file that is not `*.md` or `LICENSE*` |
| Just Parse | `Justfile`, `iso.justfile`, `just/` |

The plain and LUKS install tests build the same ISO and use different install
paths. A change to their shared inputs (`xfce-linux/`, the justfiles,
`scripts/lib-install-qemu.sh`, `scripts/embed-payload.sh`) runs one of
the two tests. The run number selects the test. Set the repository variable
`E2E_ROUND_ROBIN_SIZE` to 2 to run both. A change to the install script or
workflow of one test always runs that test. The two tests run fully on their
weekly schedules and on manual dispatch.

## Rollback

`rollback-stable.yml` runs only through manual dispatch and defaults `dry_run`
to true. It needs the approved key pair.
The workflow resolves the SHA tag to an immutable registry digest and verifies its signature.

It needs ISO, plain and LUKS qualification artifacts for the same commit and digest.
Missing artifacts and old-payload tests fail this gate.
It also completes the `CRITICAL,HIGH` scan and SARIF upload.
If a command fails, the workflow does not write release tags.
The existing report-only findings policy does not qualify a vulnerable image.

With `dry_run=false`, `skopeo copy --preserve-digests` sets `:stable` and its
dated rollback tag from that exact digest. Then the workflow force-pushes the
stable branch to the same commit. It shares the promotion concurrency group.
The key pair and a policy for bootc signatures remain external prerequisites.
See the [signature guide](signing.md).

### Serial log permissions in install E2E (#135)

| Symptom | Cause | Fix / invariant |
| --- | --- | --- |
| Plain installed boot times out, then `tail` reports `Permission denied` (run 39399656661) | QEMU runs under sudo and can create root-owned 0600 serial logs; unprivileged readers never see readiness or emergency markers | Read live serial logs with sudo. The plain-installed path runs the shared Python serial classifier with sudo, matching QEMU and the LUKS unlock helper. |

The earlier missing `:latest` publication failure is distinct: merged #147
unblocked the build and #241 restored scheduled publication. The October 20
Plain run successfully built its ISO and booted QEMU before this log-access
failure. This fix does not resolve all guest boot failures.

### Media binding, signing, and candidate qualification (November 2026)

| Symptom | Cause | Fix / invariant |
| --- | --- | --- |
| Plain run 41449240676 installs and reboots, but reports a five-minute boot timeout | ANSI escapes between `Started` and `gdm.service` defeat the raw grep predicate, although GDM started | Reuse `qemu_check_serial` through `wait-boot`, then require the strict GUI gate. A login prompt alone never passes. |
| Changed-element run 41445803428 fails in `libbluray` fetch with a Dulwich `ValueError` | VideoLAN's Git endpoint returns an Anubis HTML challenge, not Git references | Use the same 1.5.0 release from VideoLAN's official download server, pinned by SHA256. The archive includes `contrib/libudfread`, so no separate Git module is needed. |
| ISO assembly in PR run 41392561078 fails with `unknown flag: --dest-force-compress-format` | Ubuntu 24.04 supplies Skopeo 1.13.3, which lacks that newer flag | Use supported `--dest-compress-format gzip` and exercise `/usr/bin/skopeo` 1.13.3, not the newer Homebrew binary. |
| ISO 41333027065 built successfully, but cosign failed with `create bundle file: open : no such file or directory` | cosign 3 ignores deprecated detached signature/certificate output flags and requires a bundle path | Produce and publish `.sigstore.json`; boot-gate before signing or upload. |
| PR 264 plain and LUKS live boots reached the ready marker and GUI, then fisherman refused installation | Old ISO producer embedded a VFS graph but did not provide the required `media-input.json` + read-only OCI source | Embed one immutable OCI layout and bind the generated contract to its actual platform manifest; empty recipe image selects the verified media source. |

A local smoke copied the real image
`sha256:84594ac69abd7c8ac953d4588d7e92a078bef8d36991e8ade7dcd8a558d3d7da`.
It verified every embedded blob's size and SHA256 (3,318,107,811 bytes).
This verifies media assembly, not guest boot or installation.
The corrected producer also passed a full copy with `/usr/bin/skopeo` 1.13.3.
That smoke verified every blob's size and hash, and confirmed gzip for all layers.

The same generated media passed fisherman's actual strict
`PreflightBoundOCIMediaInput` at revision
`8f0d194b5d024361e7d1ecb4e2c4c15fec0b9e66`, built from upstream source.
The smoke used a private mount namespace with `mount -o bind,ro`; `findmnt`
reported read-only and a write failed with `Read-only file system`.
Live media makes the payload read-only with a bind mount.
The mount must succeed before the display manager and ready marker.
A writable live overlay alone does not meet the contract.

Install tests now invoke fisherman directly.
Both composefs and native bootc paths use the binary shipped in the live ISO.
Neither path builds fisherman from a local checkout.
Both scripts reject the removed `fisher_repo` argument.
Each script shows the journal for the live desktop before install.

We removed the old wrapper that converted hostname failures to success.
We also removed its changes to unrelated services.
Qualification must expose any other installer failures.

For exact-candidate qualification, manually dispatch `build-multirunner.yml`
on the branch with `push_image=true`. It publishes only its SHA tag.
Use that exact reference as `payload_image` for the three workflows on the same branch:
`build-iso.yml`, `test-plain-install.yml` and `test-luks-install.yml`.
Branch ISO runs never upload to release R2 paths.
With `skip_upload=false`, the run signs through OIDC and retains the bundle as an artifact.
The chained ISO build uses the image workflow's SHA tag, never a moving latest tag.

The reusable build uses a pinned revision of the bst-ci cache fix.
Source caches use the same HOME path as `just bst`.
CAS archives no longer duplicate sources.
Architecture and configuration participate in cache keys.

Final, fallback and changed-element builds restore the newest snapshot for the same graph hash,
then fall back to the same image, runner OS and architecture.
Each stage saves a unique key for its run and try, even after a failed build.
This keeps new sources in the cache. Later builds can restore more than the first seed.

The Brussels identity does not rename `project.conf` or the
`cache-xfce-linux-*` registry namespaces.

Shared uploads stop leftover builders before they archive the CAS.
The pinned image and actual workspace mounted at `/src` identify this job's containers.
Builders for another workspace remain active.
They omit daemon logs and sockets; a separate artifact contains the full build logs.

A native smoke used two BusyBox containers with different workspaces.
Both used the same image ID.
The actual helper stopped only its own container and left the other one active.
The smoke removed both test containers afterward; it did not run a full BuildStream build.

### Bounded PR build evidence

Run 41449241146 hit its 100-minute budget with exit 124.
Console output stopped at 13:15:33; the job timed out at 14:47:41.
It did not identify a compiler failure.
The artifact had only the console log.

PR jobs now stop their builders before they copy logs.
The archive keeps logs for each element and for `_casd`.
A real smoke ran the actual step with the pinned builder.
It copied eight files, including logs from the CAS daemon.
The leaf log matched its source by SHA256.
This checks retention of logs, not a complete OS build.

### Composefs source preparation

The producer follows dakota-iso's source-only preparation contract.
It injects valid TOML at `/usr/lib/bootc/install/00-defaults.toml`:
`root-mount-spec = "LABEL=root"` under `[install]`.
After a full squash, it reads the actual layer diffid.
It writes that value as both the `ostree.final-diffid` label and OCI annotation.
It publishes the local cache tag only after those values match the final layer.
No live user, installer, Flatpak, or debug configuration enters this payload.

A bounded smoke used Python's image for Alpine, with four layers.
Podman prepared a layer and preserved the inherited command.
Skopeo 1.13.3 exported that layer with gzip and both diffid fields intact.
The smoke verified all blob hashes and sizes, and extracted the exact root-mount TOML.
A second invocation reused the prepared image without any build output.
This verifies the transformation, not the TunaOS installation.

Run 41449240676 built both ISOs and completed LUKS E2E with the old published payload.
It installed, rebooted, unlocked LUKS, and captured the post-unlock desktop.
The prompt was text, and the desktop still had black regions.
This does not qualify the final Brussels candidate or its visual appearance.

Plain installation also completed and rebooted.
GDM had started, but ANSI escapes defeated the raw grep predicate.
The actual artifact returned `gdm` through the shared classifier under sudo.
The plain path now uses that classifier through `wait-boot`.
It still needs the strict GUI gate and rejects a login prompt alone.

Frozen source `eb22bb3` then passed plain run 41456541509 and LUKS run 41456542014.
Both used the old immutable payload, not the new Brussels image.
The checks for GDM and the GUI passed after reboot.

PR 264 remains a draft until exact-candidate and visual qualification pass.

### Desktop appearance and wallpaper defaults

The current source artwork uses an original yellow iris with sword leaves.
It replaces the abstract arches and credits Xfce and TunaOS in the wordmark.
It does not copy the official regional emblem, Xfce logo or Atomium.
The icon, wordmark and wallpaper share the same iris paths.
Native SVG renders and wordmark OCR passed.
LUKS tests have not yet verified this artwork in a built image.

The Brussels wallpaper has an Xfconf system default under
`files/etc-config/usr/etc/xdg/xfce4/xfconf/xfce-perchannel-xml/xfce4-desktop.xml`.
It uses the supported format with numeric monitors.
Upstream xfdesktop migrates `screen0/monitor0/image-path` to the actual monitor
name and creates a `last-image` property for each workspace.
Existing user properties take precedence.
This avoids a QEMU-specific connector name or a developer-path symlink.

Live installer entries use the Brussels logo by default, not a generic installation icon.
The image's `os-release` and Plymouth defaults also select Brussels identity and artwork.

A real D-Bus session with `xfconf-query` loaded the Brussels path from this file.
It also accepted and retained a user-selected override.
This checks configuration behavior, not the visual result.

The [earlier installed screenshot from run 41449240676](https://raw.githubusercontent.com/tuna-os/xfce-linux/ci-screenshots/luks-e2e/41449240676/stable/final-boot.png)
shows desktop icons but mostly black pixels and fragments of wallpaper.
It does not prove a healthy desktop or the new Brussels appearance.

Headless QEMU omitted an explicit graphics device.
Its journal showed llvmpipe and unsupported DRM features.
The existing VNC recipe used `virtio-vga`.
Headless live, installed, serial and production boots now select that same device.

Plain run 41461329467 used the same immutable payload and passed.
Its [inspected image](https://raw.githubusercontent.com/tuna-os/xfce-linux/ci-screenshots/plain-e2e/41461329467/stable/final-boot.png)
shows the full wallpaper, icons and both panels, without the black regions.
This checks the VM graphics setup, not the new Brussels appearance.
The compositor source and renderer policy have not changed.

The hosted runner for LUKS run 41461329227 lost its server connection.
GitHub retained no logs or artifacts from that try.
There is no guest result from that try.

The unchanged frozen source and payload passed on the fresh-worker retry
(try 2, job 125371824325), including shipped fisherman installation,
passphrase entry and installed boot.
Its [inspected installed image](https://raw.githubusercontent.com/tuna-os/xfce-linux/ci-screenshots/luks-e2e/41461329227/stable/final-boot.png)
shows the complete desktop, matching the plain test's graphics repair.
The prompt image is still a text console, not a branded Plymouth scene.
These tests use the old pinned image, not the new Brussels source image.

The pinned desktop executable contains a fallback path under its developer's
`/var/home/james/dev/xfce-wayland/install` prefix.
We did not add a compatibility symlink for that path.
The inherited binary import still has other compatibility paths for that prefix.
The desktop is still imported as binaries, not rebuilt from source.
The new candidate still needs visual and installation qualification.

Live GUI checks fail if the screen remains dark or unstable until the timeout.
A retained bright frame is diagnostic only, not success.
Screenshot write failures also propagate.
The production ISO gate uses the same checker before it creates a PNG.
It does not save PPM data with a `.png` suffix.
Pixel stability still does not prove desktop health; inspect the actual image.

### Authoritative libbluray source transport

[VideoLAN's project page](https://www.videolan.org/developers/libbluray.html)
links its [official 1.5.0 release archive](https://download.videolan.org/pub/videolan/libbluray/1.5.0/libbluray-1.5.0.tar.xz).
The SHA256 is `f676408e91a5d321abf8b8d4dfdae36205c297dab5c54c3ec519639025f474a2`.
This keeps version 1.5.0 and its bundled libudfread source.
It does not invent another mirror or hide a fetch exception.

The GNOME patch queue replaces the two Git sources with that archive.
The pinned builder ran a source fetch with this patch.
It fetched and verified the archive.
The smoke used an isolated cache and `--deps none --ignore-project-source-remotes`.
It processed one leaf without errors in nine seconds.
This checks source retrieval and graph integration, not a complete OS build.

### Authoritative publication digest and trust gates

Main run 41378878578 completed the OS build, export, lint and publish.
It did **not** qualify security.
Trivy read the local digest
`sha256:132858d09339056d5006d6cd67da0fea21cd33133d49f9d9398636943ba483e2` and received `MANIFEST_UNKNOWN`.
The registry resolved the SHA tag to
`sha256:6409a488869c09e7a327483f710d9cbfe7f7da30b8bbf763a23f93ab5c9e3056`.
The workflow ignored the scan failure and missing SARIF.
It published the image without a signature because `SIGNING_SECRET` was absent.

Publishers now capture the digest at the push destination.
If the scanner or SARIF upload fails, the job fails.
The configuration keeps `CRITICAL,HIGH` and report-only CVE results.
Actual findings still block qualification for security, even if the build passes.

The manual fallback no longer updates `latest`.
It does not retry failed pushes.
Release and rollback gates verify the approved key pair and the image's
signature before they change mutable tags or branches.
Stable promotion retags the nightly image after it verifies the digest.
See the [signature guide](signing.md) for the native smoke and administrator prerequisites.

Image build 41476620423 started from source
`f28839d9567ad5c80589a83230be4666f7fdce64` after the original main run finished.
This preserved work in the cache.
That source predates these publisher/security gate repairs.
A successful build alone does not qualify security or the new Brussels image.

### Large ISO signatures and exact qualification

Run 41474270502 built and booted a 6.56 GB ISO, then cosign exited 137.
Cosign 3.0.6 reads the whole artifact into RAM when it signs or verifies a file.
The official Python CLI from Sigstore streams the actual ISO hash.
It signs a standard bundle with GitHub OIDC, not a checksum file.
The verifier streams the ISO hash and uses cosign's supported digest input.

It keeps the exact workflow identity, GitHub issuer and transparency checks.
See [large ISO memory use](signing.md#large-iso-memory-use).

The ISO producer records the actual immutable source in `qualification.json`.
It keeps that source separate from the installed system's update channel.
CI copies this record from `/var/iso-build` beside the ISO before it uploads evidence.
Promotion and rollback compare all three records with the signed commit and digest.
Missing records cannot authorize a release, nor can tests that use an older payload.
