# Image signatures

Brussels will sign its OCI images with a cosign key, not a keyless
signature. CI does not sign images yet: no key pair exists, `cosign.pub` is
not in the repository, and the sign step skips (see "Before the key exists").

## Why a key

`bootc` verifies an image through
[containers-policy(5)](https://github.com/containers/image/blob/main/docs/containers-policy.json.5.md).
Its `sigstoreSigned` requirement takes a public key on disk:

```json
{ "type": "sigstoreSigned", "keyPath": "/usr/share/pki/containers/brussels.pub" }
```

No policy type can express both a Fulcio certificate identity and an OIDC
issuer, which is what a keyless signature carries. A person who runs
`cosign verify` can check such a signature. The tool that consumes the
image cannot. This repository moved off keyless for that reason.

`zirconium-dev/zirconium-hawaii` reached the same conclusion. Its
`cosign.pub` and `/usr/share/pki/containers/` layout is the model here.

## Create the key

A maintainer with repository admin runs one command. It creates the pair and
sends the private half straight to GitHub Actions secrets. The key therefore
stays out of a shell history, and out of a file that someone must remember
to delete:

```bash
cosign generate-key-pair github://tuna-os/brussels
```

That command writes `cosign.pub` to the current directory. It also sets two
repository secrets, `COSIGN_PRIVATE_KEY` and `COSIGN_PASSWORD`.

This repository's workflow reads `SIGNING_SECRET` and
`SIGNING_SECRET_PASSWORD`. So either rename those two secrets, or create the
pair locally and set them by hand:

```bash
cosign generate-key-pair
gh secret set SIGNING_SECRET          -R tuna-os/brussels < cosign.key
gh secret set SIGNING_SECRET_PASSWORD -R tuna-os/brussels
rm -f cosign.key
git add cosign.pub && git commit -m "chore: add the image signature public key"
```

Commit `cosign.pub`. It is the public half, and it belongs in the repository.

## Before the key exists

The workflow runs its sign step only when `SIGNING_SECRET` holds a value.
Without that secret the build still publishes and the sign step reports
skipped. The build logs a warning:

```
::warning::SIGNING_SECRET is not set — published an unsigned image.
```

You can therefore see an unsigned publish in the log.

## Still to do

The image does not yet carry the public key or a policy file, and that
change cannot land before `cosign.pub` exists. It needs an element much like
zirconium's `elements/zirconium/common.bst`:

- copy `cosign.pub` to `/usr/share/pki/containers/brussels.pub`
- ship `/etc/containers/policy.json` with a `sigstoreSigned` entry for
  `ghcr.io/tuna-os/brussels` that names that `keyPath`
- add a second `sigstoreSigned` entry with the same `keyPath` for the alias
  `ghcr.io/tuna-os/xfce-linux` (see "Two names, one key")
- add `/etc/containers/policy.json` to the element's `overlap-whitelist`,
  because the base layer ships one

Until that change lands, the installed system does not enforce a signature,
even after CI signs images.

## Two names, one key

The image has two names during the transition in
[`migration-brussels.md`](migration-brussels.md): `ghcr.io/tuna-os/brussels`
and the alias `ghcr.io/tuna-os/xfce-linux`. Both names point to one digest.

A signature does not move with the digest. cosign stores the signature in
the repository that it signs. The signature also records that name as its
identity, and `containers-policy(5)` compares that identity with the name
that the client pulls (`matchRepoDigestOrExact` by default). A system that
pulls `xfce-linux` therefore needs a signature made for `xfce-linux`.

The sign step in `build-multirunner.yml` signs the digest one time for each
name in `PUBLISH_NAME` and `ALIAS_NAMES`, with the same key. The policy
file then has one entry for each name:

```json
{
  "transports": {
    "docker": {
      "ghcr.io/tuna-os/brussels": [
        { "type": "sigstoreSigned", "keyPath": "/usr/share/pki/containers/brussels.pub" }
      ],
      "ghcr.io/tuna-os/xfce-linux": [
        { "type": "sigstoreSigned", "keyPath": "/usr/share/pki/containers/brussels.pub" }
      ]
    }
  }
}
```

Do not enable the policy for one name only. A system on the other name
would then fail each update.

## Verify an image

```bash
cosign verify --key cosign.pub ghcr.io/tuna-os/brussels:latest
cosign verify --key cosign.pub ghcr.io/tuna-os/xfce-linux:latest   # alias
```

## Live ISOs

`build-iso.yml` still signs ISO artifacts without a key, which is correct. A
person verifies an ISO; `bootc` does not. The
`--certificate-identity-regexp` instructions in README.md still apply to
those files.
