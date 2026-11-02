# Image signatures

Brussels (TunaOS) retains this repository's trust model with keys for OCI images.
CI publishes candidates as experimental images with SHA tags and no signatures.
These candidates do not qualify for security.
CI blocks the release channels until an administrator provides the approved key pair.
CI does not generate keys or replace the trust root.

## Why a key

`bootc` verifies an image through
[containers-policy(5)](https://github.com/containers/image/blob/main/docs/containers-policy.json.5.md).
Its `sigstoreSigned` requirement takes a public key on disk:

```json
{ "type": "sigstoreSigned", "keyPath": "/usr/share/pki/containers/xfce-linux.pub" }
```

No policy type can express both a Fulcio certificate identity and an OIDC
issuer, which is what a keyless signature carries. A person who runs
`cosign verify` can check such a signature. The tool that consumes the
image cannot. This repository moved off keyless for that reason.

`zirconium-dev/zirconium-hawaii` reached the same conclusion. Its
`cosign.pub` and `/usr/share/pki/containers/` layout is the model here.

## Provision the approved key pair

An administrator must approve the trust root, commit its public half as
`cosign.pub`, and grant this repository the matching `SIGNING_SECRET`.
For an encrypted key, the administrator must also grant `SIGNING_SECRET_PASSWORD`.
The workflow maps those secrets to `COSIGN_PRIVATE_KEY` and `COSIGN_PASSWORD`.
Never paste a private key into an issue or chat.

In November 2026, neither secret was present at repository or organization scope
for `xfce-linux`. The repository also had no committed `cosign.pub`.
The organization does have
[`tuna-os/tunaOS/cosign.pub`](https://github.com/tuna-os/tunaOS/blob/0b577a9eb2d83b49eecbaf25d083f458e003e70b/cosign.pub)
and a repository-local `SIGNING_SECRET` in that different repository.
That does not grant Brussels its private half or approve that trust root here.
GitHub lists names for secrets, not their private values.
An administrator must grant access; CI cannot invent a new key.

`check-release-signing.sh` refuses absent keys.
It checks cosign's public key against the committed file.
This gate runs before CI changes mutable tags or the stable branch.
No force override exists.

## Publication and promotion gates

`push-image.sh` captures the **destination** digest from `podman push
--digestfile`. A local `podman inspect .Digest` is not authoritative.
Run 41378878578 published a manifest with a different digest.
Trivy read the local digest and received `MANIFEST_UNKNOWN`.
The workflow ignored both the scan failure and the SARIF upload error.

Every publisher scans the actual digest for its SHA candidate.
CI fails if the scanner or SARIF upload fails.
The configuration keeps `CRITICAL,HIGH` and report-only CVE results.
A build pass does not qualify an image with vulnerabilities.

Main signs and verifies the exact digest with the approved public key
before it updates channel tags. Stable reuses that signed image.
Stable promotion reuses the nightly digest and does not build the OS again.

Promotion and rollback also need successful ISO, plain and LUKS runs for that commit.
Each run records the pinned source image, its revision label and the workflow commit.
All three records must match the signed image digest and commit before tags or branches move.
Old-payload smoke runs cannot satisfy this gate, even if they pass on newer workflow code.
Rollback verifies and scans its qualified target before it changes tags or branches.

Images from the manual fallback have no signatures.

A native Podman/Skopeo smoke pushed a bounded fixture to an isolated registry.
It checked the candidate push, channel push and inspection of the remote tag.
All three checks returned
`sha256:131905bf808fe29b4a54ad0541945a978d835d4a4cb223ff182dc3fb3e8adbc5`.
The release preflight failed because `SIGNING_SECRET` was absent.
This checks the digest contract and negative gate.
We have not verified a successful OCI signature: the approved key pair is
still unavailable.

A candidate without a signature does not qualify for security,
even if its build and installer tests pass.

## Installed verification boundary

The image does not yet carry the public key or a policy file, and that
change cannot land before `cosign.pub` exists. It needs an element much like
zirconium's `elements/zirconium/common.bst`:

- copy `cosign.pub` to `/usr/share/pki/containers/xfce-linux.pub`
- ship `/etc/containers/policy.json` with a `sigstoreSigned` entry for
  `ghcr.io/tuna-os/xfce-linux` that names that `keyPath`
- add `/etc/containers/policy.json` to the element's `overlap-whitelist`,
  because the base layer ships one

Until that change lands, the installed system does not enforce a signature,
even after CI signs and verifies an image.
Keys alone do not qualify the security of updates with bootc.
Hashes from the OCI layout bind the content of media.
They do not authenticate a publisher without a signature.

## Verify an image

```bash
cosign verify --key cosign.pub ghcr.io/tuna-os/xfce-linux:latest
```

## Live ISOs

`build-iso.yml` signs ISO artifacts through GitHub OIDC into a
`.sigstore.json` bundle, then verifies the exact workflow identity and issuer
before publication. This does not change the OCI trust model: a person verifies
an ISO; `bootc` does not consume its bundle. README.md shows the verification
command. Stable promotion also verifies the published ISO bundle.

## Large ISO memory use

Run 41474270502 built the 6.56 GB ISO and passed its UEFI boot gate.
Its cosign 3.0.6 process then received SIGKILL and exited 137.
The default
[`sign-blob` implementation](https://github.com/sigstore/cosign/blob/v3.0.6/cmd/cosign/cli/sign/sign_blob.go)
reads the whole artifact into RAM.
The file path in
[`verify-blob`](https://github.com/sigstore/cosign/blob/v3.0.6/cmd/cosign/cli/verify/verify_blob.go)
also reads the whole artifact.

ISO CI now uses the official Python CLI from Sigstore, version 4.5.1.
`.github/requirements-sigstore.txt` pins that CLI and its runtime dependencies.
Its hash implementation uses a 128 KiB buffer and signs the artifact digest.
It produces the same Sigstore MessageSignature bundle, with GitHub OIDC,
Fulcio identity and Rekor proof. It does not sign a checksum text file.

`verify-iso-signature.sh` hashes the actual ISO as a stream.
It passes `sha256:<actual digest>` to cosign's supported digest input.
The workflow identity, OIDC issuer and transparency checks remain mandatory.
README.md shows the equivalent command for a download.
CI also checks that the same bundle rejects a truncated copy of the ISO.
The full-size OIDC proof must pass before this repair qualifies the ISO.
