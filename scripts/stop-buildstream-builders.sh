#!/usr/bin/env bash
# A timed-out client can leave its builder active. Never stop another workspace.
set -euo pipefail
if [ "$#" -ne 2 ]; then
    echo "Usage: $0 PINNED_BUILDER_IMAGE WORKSPACE" >&2
    exit 2
fi
builders=$(podman ps --quiet --filter "ancestor=$1")
workspace=$(realpath "$2")
for builder in $builders; do
    if mount_source=$(podman inspect --format '{{range .Mounts}}{{if eq .Destination "/src"}}{{.Source}}{{end}}{{end}}' "$builder"); then
        if [[ "$mount_source" == "$workspace" ]]; then
            podman stop --ignore --time 30 "$builder"
        fi
    else
        status=0
        podman container exists "$builder" || status=$?
        # An auto-removed container has already stopped; other errors fail.
        [[ "$status" == 1 ]] || exit 1
    fi
done
