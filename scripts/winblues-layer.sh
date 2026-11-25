#!/usr/bin/env bash
# Make the brussels-winblues layer without BuildStream, and add it to an
# existing base image. For screenshots and quick tests only: CI builds the
# layer with BuildStream (just export-variant).
#
# It runs the install-commands of elements/winblues/chicago95.bst, with no
# changes, in the base image. It needs python3 with PyYAML. Run it as root if
# the image is for `just generate-bootable-image`, which uses root storage.
set -euo pipefail

if [[ $# -ne 3 ]]; then
	echo "Usage: $0 <base image> <Chicago95 checkout at the ref of chicago95.bst> <output tag>" >&2
	exit 2
fi
base=$1 source=$(realpath "$2") tag=$3
repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

ref=$(sed -n 's/^ *ref: .*-g\([0-9a-f]*\)$/\1/p' "$repo/elements/winblues/chicago95.bst")
if [[ $(git -C "$source" rev-parse HEAD) != "$ref" ]]; then
	echo "The Chicago95 checkout is not at $ref." >&2
	exit 1
fi

python3 - "$repo/elements/winblues/chicago95.bst" >"$work/layer.sh" <<'PY'
import sys

import yaml

with open(sys.argv[1]) as f:
    script = "\n".join(yaml.safe_load(f)["config"]["install-commands"])
for name, value in {"install-root": "/out", "datadir": "/usr/share", "build-root": "/src"}.items():
    script = script.replace("%{" + name + "}", value)
assert "%{" not in script, "a BuildStream variable has no value"
print("cd /src\n" + script)
PY

mkdir "$work/out"
podman run --rm --network none --security-opt label=disable \
	-v "$source:/src:ro" -v "$work/out:/out" -v "$work/layer.sh:/layer.sh:ro" \
	"$base" sh -e /layer.sh
cp -r "$repo/files/winblues/." "$work/out/"
podman build --pull=never --security-opt label=type:unconfined_t \
	--build-arg "BASE_IMAGE=$base" -f "$repo/variants/winblues/Containerfile" \
	-t "$tag" "$work/out"
