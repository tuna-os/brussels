#!/usr/bin/env bash
# Pin the image before building, and retain the exact source/payload relationship.
set -euo pipefail
if [ "$#" -lt 3 ] || [ "$#" -gt 4 ]; then
    echo "Usage: $0 PAYLOAD_REF QUALIFICATION_JSON SOURCE_COMMIT [SOURCE_OVERRIDE]" >&2
    exit 2
fi
reference=${4:-$(tr -d '[:space:]' < "$1")}
image=$(skopeo inspect --override-os linux --override-arch amd64 "docker://${reference}")
immutable=$(jq -er '.Name + "@" + .Digest' <<<"$image")
jq -n --arg source_commit "$3" --arg payload_image "$immutable" \
    --arg payload_revision "$(jq -r '.Labels["org.opencontainers.image.revision"] // ""' <<<"$image")" \
    '{source_commit:$source_commit, payload_image:$payload_image, payload_revision:$payload_revision}' > "$2"
cat "$2"
