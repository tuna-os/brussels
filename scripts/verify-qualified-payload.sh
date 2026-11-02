#!/usr/bin/env bash
# A green workflow alone cannot prove which image was actually installed.
set -euo pipefail
if [ "$#" -ne 5 ]; then
    echo "Usage: $0 SOURCE_COMMIT IMAGE_AT_DIGEST ISO_RUN PLAIN_RUN LUKS_RUN" >&2
    exit 2
fi
sha=$1
image=$2
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
workflows=(build-iso.yml test-plain-install.yml test-luks-install.yml)
names=(iso-qualification plain-qualification-stable luks-qualification-stable)
runs=("$3" "$4" "$5")
for index in 0 1 2; do
    run=${runs[$index]}
    gh api "repos/{owner}/{repo}/actions/runs/${run}" | jq -e \
        --arg sha "$sha" --arg workflow ".github/workflows/${workflows[$index]}" \
        '.head_sha == $sha and .path == $workflow and .status == "completed" and .conclusion == "success"' >/dev/null
    gh run download "$run" --name "${names[$index]}" --dir "$tmp/$index"
    jq -e --arg sha "$sha" --arg image "$image" \
        '.source_commit == $sha and .payload_revision == $sha and .payload_image == $image' \
        "$tmp/$index/qualification.json" >/dev/null || {
        echo "::error::Run ${run} did not qualify commit ${sha} with ${image}" >&2
        exit 1
    }
done
gh run download "$5" --name brussels-visual-stable --dir "$tmp/visual"
jq -e --arg sha "$sha" --arg image "$image" \
    '.branding_qualified == true and .proof_class == "observer-assisted" and
     .source_commit == $sha and .payload_image == $image and
     .observations.installed.boot_id != .observations.live.boot_id' \
    "$tmp/visual/journey.json" >/dev/null
