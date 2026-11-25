# Secure Boot test fixtures

`gnome-build-meta-snakeoil-vendor.crt` is the public test certificate
`files/boot-keys/snakeoil/SECURE_BOOT_VENDOR_CRT` of GNOME/gnome-build-meta
(read at commit `53c084e17b2d71227def3e5bfa727c4a531e2816`). The private key
of that certificate is public in the same directory, so a signature from it
proves nothing.

The BuildStream build signs systemd-boot with that key. The publish job
removes the signature. `verify-image.sh --reject-cert` uses this file to
prove that no boot file of a published image verifies against it.

This directory holds no private key.
