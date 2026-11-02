# Local Mkosi DDI (experimental)

Brussels has a separate path for raw-GPT images. This path is experimental.
It does not replace the live ISO or bootc `install to-disk`.
Do not use it for a supported installation or upgrade.
The repository and image identity remain `xfce-linux`.

## Build locally

Install Mkosi 26 or newer and systemd-repart.
Also install the project's dependencies for Podman and BuildStream.
Run from the repository root:

```sh
just mkosi-ddi
```

The recipe builds one compose target, `mkosi/xfce-linux-ddi.bst`, with `just bst`.
It shares the BuildStream container and `$HOME/.cache/buildstream` with other builds.
It does not create another cache.

It checks out the runtime into disposable `.mkosi-root`.
Mkosi's stable `Distribution=custom` backend consumes that tree through `BaseTrees=`.
This avoids a dependency on `bst` inside Mkosi's sandbox.
The recipe selects the initramfs from the newest kernel in that tree.
It does not build an initramfs from unrelated host packages.
The recipe fails if the kernel or initramfs is absent.

`files/etc/os-release` supplies the same Brussels/TunaOS identity as the OCI build.
The repart layout declares an EFI partition of 512 MiB.
It also declares an ext4 root partition of at least 8 GiB.
Mkosi installs systemd-boot.

Output is `mkosi/ddi/mkosi.output/xfce-linux-ddi.raw`.
Run `just mkosi-ddi-clean` to remove local outputs and the disposable checkout.
This recipe does not push, sign or publish anything.
It preserves BuildStream's shared cache.

## Evidence and limits

The review exercised the Mkosi 27.1 configuration parser.
It did not assemble or boot the full DDI.
The GNOME OS initramfs must still demonstrate root discovery for this ext4 layout.
EFI, desktop startup, and reboot also need qualification.
The presence of bootc does not imply bootc deployment or update semantics.

Full OS builds and KVM qualification need CI runners with enough disk space.
The review host has no `/dev/kvm` and cannot hold a full world build.
The main OCI/live/plain/LUKS pipeline remains independent of this experimental output.
