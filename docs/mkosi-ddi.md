# Local Mkosi DDI (experimental)

Brussels has a separate, experimental raw-GPT image path. It does not replace
the live ISO or bootc `install to-disk`, and is not a supported installation or
upgrade path. The repository and image identity remain `xfce-linux`.

## Build locally

Install Mkosi 26 or newer, systemd-repart, and the normal Podman/BuildStream
project dependencies. Run from the repository root:

```sh
just mkosi-ddi
```

The recipe builds the single compose target `mkosi/xfce-linux-ddi.bst` using
`just bst`, so it shares the normal containerized BuildStream configuration and
`$HOME/.cache/buildstream` rather than starting another independent build/cache.
It checks out the runtime into disposable `.mkosi-root` and passes that tree to
Mkosi's stable `Distribution=custom` backend through `BaseTrees=`. This avoids
assuming a `bst` binary and project root exist inside Mkosi's default tools
sandbox. The matching initramfs is taken from that tree's newest kernel, not
built using unrelated host packages. Missing kernel/initramfs fails the recipe.

`files/etc/os-release` overlays the same Brussels/TunaOS identity used by the
OCI build. The repart layout declares a 512 MiB EFI System Partition and an
ext4 root partition of at least 8 GiB. Mkosi installs systemd-boot.

Output is `mkosi/ddi/mkosi.output/xfce-linux-ddi.raw`. To remove local outputs
and the disposable checkout, run `just mkosi-ddi-clean`. This recipe does not
push, sign or publish anything. BuildStream's shared cache is not removed.

## Evidence and remaining qualification

The Mkosi 27.1 configuration parser has been exercised against this configuration.
The full DDI has not been assembled or booted. In particular, the GNOME OS
initramfs must still be shown to discover and mount this non-bootc ext4 root,
and EFI, desktop startup, and reboot remain unqualified. Do not infer bootc
deployment/update semantics from the presence of bootc in the root tree.

Full OS builds and KVM qualification belong on sufficiently sized CI runners;
the review host has no `/dev/kvm` and cannot hold a full world build. The main
OCI/live/plain/LUKS pipeline remains independent of this experimental output.
