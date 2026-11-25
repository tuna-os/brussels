#!/usr/bin/env bash
# Publish alias names for an image that is already on the registry.
#
# Usage: scripts/publish-alias.sh <registry> <primary> "<alias ...>" "<tag ...>"
#   e.g. scripts/publish-alias.sh ghcr.io/tuna-os brussels "xfce-linux" "latest nightly"
#
# For each tag, copy <registry>/<primary>:<tag> to <registry>/<alias>:<tag>
# on the registry side, then read both digests back and compare them. The
# copy keeps the manifest bytes (--preserve-digests), so the alias is the
# same image, not a rebuild. A mismatch or a failed copy exits non-zero:
# an alias that goes stale strands the systems that track it.
#
# SKOPEO overrides the command (CI sets "sudo skopeo" to share podman's
# registry login).
set -euo pipefail

registry="${1:?usage: $0 <registry> <primary> \"<alias ...>\" \"<tag ...>\"}"
primary="${2:?missing primary image name}"
aliases="${3-}"
tags="${4:?missing tag list}"
read -r -a skopeo <<<"${SKOPEO:-skopeo}"

digest_of() {
    "${skopeo[@]}" inspect --no-tags --format '{{.Digest}}' "docker://$1"
}

for alias in ${aliases}; do
    if [ "${alias}" = "${primary}" ]; then
        echo "::error::alias '${alias}' is the primary name" >&2
        exit 1
    fi
    for tag in ${tags}; do
        src="${registry}/${primary}:${tag}"
        dst="${registry}/${alias}:${tag}"
        ok=false
        for attempt in 1 2 3; do
            if "${skopeo[@]}" copy --all --preserve-digests "docker://${src}" "docker://${dst}"; then
                ok=true
                break
            fi
            echo "alias copy attempt ${attempt} for ${dst} failed; retrying" >&2
            sleep $((attempt * 5))
        done
        if [ "${ok}" != true ]; then
            echo "::error::could not publish alias ${dst}" >&2
            exit 1
        fi
        want="$(digest_of "${src}")"
        got="$(digest_of "${dst}")"
        if [ -z "${want}" ] || [ "${want}" != "${got}" ]; then
            echo "::error::alias digest mismatch: ${src}=${want} ${dst}=${got}" >&2
            exit 1
        fi
        echo "alias ${dst} == ${src} @ ${got}"
    done
done
