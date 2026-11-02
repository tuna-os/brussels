#!/usr/bin/env bash
# Embed the one verified OCI source consumed by fisherman on live media.
set -euo pipefail

root=${1:?Usage: embed-payload.sh ROOT PINNED_IMAGE UPDATE_REF}
source_image=${2:?Missing immutable source image}
update_ref=${3:?Missing update-tracking image reference}
layout="$root/usr/lib/tunaos/payload"
mkdir -p "$layout" "$root/etc/bootc-installer"
# Store compressed registry layers directly, not a second expanded VFS graph.
skopeo copy --override-os linux --override-arch amd64 \
    --dest-compress-format gzip --dest-force-compress-format \
    "docker://$source_image" "oci:$layout:payload"
manifest_digest=$(jq -er '.manifests | select(length == 1) | .[0].digest' "$layout/index.json")
manifest="$layout/blobs/${manifest_digest/:/\/}"
config_digest=$(jq -er '.config.digest' "$manifest")
config="$layout/blobs/${config_digest/:/\/}"
platform=$(jq -er '.os + "/" + .architecture' "$config")
[[ "$platform" == linux/amd64 ]]
jq -n --arg image "$update_ref" --arg manifest "$manifest_digest" \
    --arg config "$config_digest" --arg platform "$platform" \
    '{schemaVersion: 1, kind: "brussels-live", image: $image,
      platformManifestDigest: $manifest, configDigest: $config,
      ociLayoutPath: "/usr/lib/tunaos/payload", targetImgref: $image,
      platform: $platform}' > "$root/etc/bootc-installer/media-input.json"
# The live environment is immutable: do not advertise writable containers stores.
rm -f "$root/etc/tuna-installer/offline-stores"
# Keep GUI selection and media binding on the exact same candidate/channel.
for catalog in "$root/etc/bootc-installer/images.json" "$root/etc/tuna-installer/images.json"; do
    jq --arg image "$update_ref" \
        '.default_image = $image | .images |= map(.imgref = $image)' \
        "$catalog" > "$catalog.tmp"
    mv "$catalog.tmp" "$catalog"
done
jq --arg image "$update_ref" '.imgref = $image | del(.local_imgref)' \
    "$root/etc/bootc-installer/recipe.json" > "$root/etc/bootc-installer/recipe.json.tmp"
mv "$root/etc/bootc-installer/recipe.json.tmp" "$root/etc/bootc-installer/recipe.json"
