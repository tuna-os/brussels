# ── BuildStream wrapper ──────────────────────────────────────────────
# Runs any bst command inside the bst2 container via podman.
# Set BST_FLAGS env var to prepend flags (e.g. --no-interactive --config ...).
# Usage: just bst build oci/xfce-linux.bst
#        just bst show oci/xfce-linux.bst
#        BST_FLAGS="--no-interactive" just bst build oci/xfce-linux.bst
[group('dev')]
bst *ARGS:
    #!/usr/bin/env bash
    set -euo pipefail
    # BST_CACHE_DIR selects a different cache directory, for example a
    # throwaway one for `just bootstrap-cache` experiments.
    CACHE_DIR="${BST_CACHE_DIR:-${HOME}/.cache/buildstream}"
    mkdir -p "$CACHE_DIR"
    # BST_FLAGS env var allows CI to inject --no-interactive, etc.
    # Word-splitting is intentional here (flags are space-separated).
    # shellcheck disable=SC2086
    podman run --rm \
        --privileged \
        --device /dev/fuse \
        --network=host \
        -v "{{justfile_directory()}}:/src:rw" \
        -v "${CACHE_DIR}:/root/.cache/buildstream:rw" \
        -w /src \
        "{{bst2_image}}" \
        bash -c 'bst --colors "$@"' -- ${BST_FLAGS:-} {{ARGS}}


# ── Build log ─────────────────────────────────────────────────────────
# Run build in background, log to /var/tmp/{{image_name}}-build.log, tail it
[group('build')]
bst-build *ARGS:
    #!/usr/bin/env bash
    set -euo pipefail
    LOG=/var/tmp/{{image_name}}-build.log
    echo "=== Build started at \$(date) ===" > "\$LOG"
    BST_FLAGS="--max-jobs \$((\$(nproc) / 2)) --fetchers \$(nproc) \${BST_FLAGS:-}"
    just bst build \${ARGS:-oci/{{image_name}}.bst} >> "\$LOG" 2>&1 &
    echo "BST PID: \$! — tailing \$LOG (Ctrl-C stops tail, build continues)"
    tail -f "\$LOG"

[group('build')]
log:
    tail -f /var/tmp/{{image_name}}-build.log

# ── Build ─────────────────────────────────────────────────────────────
# Build the OCI image, load it into podman, and chunkify the result.
[group('build')]
build:
    #!/usr/bin/env bash
    set -euo pipefail

    echo "==> Building OCI image with BuildStream (inside bst2 container)..."
    just bst build oci/{{image_name}}.bst

    just export

# ── Export ─────────────────────────────────────────────────────────────
# Checkout the built OCI image from BuildStream and load it into podman.
# Assumes `bst build oci/{{image_name}}.bst` has already completed.
#
# Uses SUDO_CMD to handle root vs non-root: CI runs as root (no sudo),
# local dev needs sudo for podman access to containers-storage.
[group('build')]
export:
    #!/usr/bin/env bash
    set -euo pipefail

    # Use sudo unless already root (CI runners are root)
    SUDO_CMD=""
    if [ "$(id -u)" -ne 0 ]; then
        SUDO_CMD="sudo"
    fi

    # CI checks the artifact out in its own step and then deletes the CAS
    # before calling this recipe, because the ~100 GB cache and the squashed
    # image do not fit on a GitHub runner together (#159). With
    # EXPORT_REUSE_CHECKOUT=1, .build-out is already the artifact and must not
    # be re-requested from BuildStream — by then the cache it would read is
    # gone. Unset, the default, keeps the original one-command behaviour for
    # local use.
    if [ "${EXPORT_REUSE_CHECKOUT:-0}" = "1" ]; then
        if [ ! -d .build-out ]; then
            echo "ERROR: EXPORT_REUSE_CHECKOUT=1 but .build-out is missing" >&2
            exit 1
        fi
        echo "==> Reusing the existing .build-out checkout..."
    else
        echo "==> Exporting OCI image..."
        rm -rf .build-out
        just bst artifact checkout oci/{{image_name}}.bst --directory /src/.build-out
    fi

    # Load the multi-layer OCI image and squash into a single layer.
    echo "==> Loading and squashing OCI image..."
    IMAGE_ID=$($SUDO_CMD podman pull -q oci:.build-out)
    rm -rf .build-out

    # Build label arguments for dynamic OCI metadata
    LABEL_ARGS=""
    if [ -n "${OCI_IMAGE_CREATED}" ]; then
        LABEL_ARGS="${LABEL_ARGS} --label org.opencontainers.image.created=${OCI_IMAGE_CREATED}"
    fi
    if [ -n "${OCI_IMAGE_REVISION}" ]; then
        LABEL_ARGS="${LABEL_ARGS} --label org.opencontainers.image.revision=${OCI_IMAGE_REVISION}"
    fi
    if [ -n "${OCI_IMAGE_VERSION}" ]; then
        LABEL_ARGS="${LABEL_ARGS} --label org.opencontainers.image.version=${OCI_IMAGE_VERSION}"
    fi

    # Squash, inject build-date VERSION_ID, and apply dynamic labels.
    DATE_TAG="$(date -u +%Y%m%d)"
    # shellcheck disable=SC2086
    printf 'FROM %s\nRUN sed -i "s/^VERSION_ID=.*/VERSION_ID=\\"%s\\"/" /usr/lib/os-release \\\n    && sed -i "s/^IMAGE_VERSION=.*/IMAGE_VERSION=\\"%s\\"/" /usr/lib/os-release\n' "$IMAGE_ID" "$DATE_TAG" "$DATE_TAG" \
        | $SUDO_CMD podman build --pull=never --security-opt label=type:unconfined_t --squash-all ${LABEL_ARGS} -t "{{image_name}}:{{image_tag}}" -f - .
    $SUDO_CMD podman rmi "$IMAGE_ID" || true

    echo "==> Export complete. Image loaded as {{image_name}}:{{image_tag}}"
    $SUDO_CMD podman images | grep -E "{{image_name}}|REPOSITORY" || true

    # Match Dakota's post-export flow so the boot image is chunkified before bootc.
    just chunkify "{{image_name}}:{{image_tag}}"

# ── Clean ─────────────────────────────────────────────────────────────
# Remove generated artifacts (disk image, OVMF vars, build output).
[group('build')]
clean:
    rm -f bootable.raw .ovmf-vars.fd
    rm -rf .build-out

# ── Containerfile build (alternative) ────────────────────────────────
[group('build')]
build-containerfile $image_name=image_name:
    sudo podman build --security-opt label=type:unconfined_t --squash-all -t "${image_name}:latest" .


# ── Variants ──────────────────────────────────────────────────────────
# Build a variant image on top of the exported base image. A variant is a
# file tree (oci/layers/brussels-<variant>.bst) laid over {{image_name}}
# by variants/<variant>/Containerfile; see docs/winblues.md.
# With EXPORT_REUSE_CHECKOUT=1 (CI), .build-out-<variant> is already checked out.
[group('build')]
export-variant variant="winblues":
    #!/usr/bin/env bash
    set -euo pipefail
    SUDO_CMD=""
    if [ "$(id -u)" -ne 0 ]; then
        SUDO_CMD="sudo"
    fi
    out=".build-out-{{variant}}"
    if [ "${EXPORT_REUSE_CHECKOUT:-0}" != "1" ]; then
        just bst build oci/layers/brussels-{{variant}}.bst
        rm -rf "$out"
        just bst artifact checkout oci/layers/brussels-{{variant}}.bst --directory "/src/$out"
    fi
    test -d "$out"
    LABEL_ARGS=()
    [ -n "${OCI_IMAGE_CREATED}" ] && LABEL_ARGS+=(--label "org.opencontainers.image.created=${OCI_IMAGE_CREATED}")
    [ -n "${OCI_IMAGE_REVISION}" ] && LABEL_ARGS+=(--label "org.opencontainers.image.revision=${OCI_IMAGE_REVISION}")
    [ -n "${OCI_IMAGE_VERSION}" ] && LABEL_ARGS+=(--label "org.opencontainers.image.version=${OCI_IMAGE_VERSION}")
    $SUDO_CMD podman build --pull=never --security-opt label=type:unconfined_t \
        --build-arg "BASE_IMAGE=localhost/{{image_name}}:{{image_tag}}" \
        "${LABEL_ARGS[@]}" \
        -f variants/{{variant}}/Containerfile \
        -t "brussels-{{variant}}:{{image_tag}}" "$out"
    rm -rf "$out"
    echo "==> Variant image loaded as brussels-{{variant}}:{{image_tag}}"
