#!/usr/bin/env bash
# Mutable release channels require the repository's declared signing material.
set -euo pipefail

public_key=${1:-cosign.pub}
if [ -z "${COSIGN_PRIVATE_KEY:-}" ]; then
    echo '::error::Release promotion requires repository secret SIGNING_SECRET (and SIGNING_SECRET_PASSWORD when encrypted).' >&2
    exit 1
fi
if [ ! -s "$public_key" ]; then
    echo "::error::Release promotion requires the approved matching public key at $public_key." >&2
    exit 1
fi

derived_key=$(mktemp)
trap 'rm -f "$derived_key"' EXIT
cosign public-key --key env://COSIGN_PRIVATE_KEY > "$derived_key"
if ! cmp -s "$public_key" "$derived_key"; then
    echo '::error::SIGNING_SECRET does not match the committed release public key.' >&2
    exit 1
fi
