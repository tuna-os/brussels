#!/usr/bin/env bash
# Print the destination digest, not the local pre-conversion manifest digest.
set -euo pipefail

if [ "$#" -ne 2 ]; then
    echo "Usage: $0 LOCAL_IMAGE DESTINATION_REF" >&2
    exit 2
fi

digest_file=$(mktemp)
trap 'rm -f "$digest_file"' EXIT
podman push --digestfile "$digest_file" "$1" "docker://$2"
cat "$digest_file"
