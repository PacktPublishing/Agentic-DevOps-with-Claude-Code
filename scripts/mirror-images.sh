#!/usr/bin/env bash
# ABOUTME: Re-hosts the platform's explicitly-referenced upstream images under a GHCR namespace,
# ABOUTME: so no manifest pulls docker.io directly and a build cannot be stopped by a rate limit.
#
# You do not need to run this. The images the manifests name are public and pull anonymously.
# Run it when you would rather host them yourself.
#
# This mirrors upstream images. It does not build the two images that have no upstream:
#   images/backstage/build-and-push.sh   the Backstage app, scaffolded and built
#   images/vllm-qwen3/build-and-push.sh  vLLM CPU with the Qwen3-1.7B weights baked in
# Both take the same GHCR_ORG. Rehosting the whole platform means running all three.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
readonly SCRIPT_DIR REPO_ROOT
readonly IMAGE_MAP="${REPO_ROOT}/image-map.tsv"

GHCR_ORG="${GHCR_ORG:-}"
DRY_RUN=0

# The images that raw manifests reference by a ghcr.io/<org>/<name> tag. Each line is
# "<upstream source>  <ghcr repo:tag under the org>". Keep this in sync with the image:
# lines in solution/platform/2-ai-plane/{vllm,llm-guard,mcp-server} and the seed Jobs. Chart
# images are NOT here: charts pull their own images from upstream, and re-hosting those needs a
# node-level pull-through cache or per-chart image overrides, not this.
#
# One of these needs a manual step afterwards. The mcp-server manifest pins its image by digest
# rather than by tag, and a copy into a different namespace produces a different digest. This
# script prints the new digest for each image it copies; take the mcp-server-everything one and
# update solution/platform/2-ai-plane/mcp-server/manifests/mcp-server.yaml. Skipping that leaves
# the pod unable to pull, citing a digest that exists nowhere.
readonly SOURCES=(
    "docker.io/vllm/vllm-openai-cpu:v0.23.0-x86_64  vllm-openai-cpu:v0.23.0-x86_64"
    "docker.io/laiyer/llm-guard-api:0.3.16          llm-guard-api:0.3.16"
    "docker.io/openbao/openbao:2.5.5                openbao:2.5.5"
    "docker.io/curlimages/curl:8.11.0               curl:8.11.0"
    "docker.io/mcp/everything:latest                mcp-server-everything:latest"
)

log() { printf '%s\n' "$*" >&2; }

usage() {
    cat >&2 <<EOF
Usage: GHCR_ORG=<org> ${0##*/} [--dry-run]

Copies each explicitly-referenced platform image to ghcr.io/\${GHCR_ORG}/<name>:<tag> with
crane. Run once before the event. --dry-run lists the copies without pushing.

Requires: crane, authed to ghcr.io with write:packages (gh auth token | crane auth login).
EOF
    exit 2
}

main() {
    [[ "${1:-}" == "--dry-run" ]] && DRY_RUN=1
    [[ "${1:-}" =~ ^(|--dry-run)$ ]] || usage
    [[ -n "${GHCR_ORG}" ]] || { log "GHCR_ORG is not set"; usage; }
    command -v crane >/dev/null 2>&1 || { log "crane not found"; exit 1; }

    local total="${#SOURCES[@]}" i=0 failed=0 src name dst digest
    log "Mirroring ${total} images to ghcr.io/${GHCR_ORG} (dry-run=${DRY_RUN})"
    # Truncate the map on a real run only. The map records what was mirrored where
    # (column 2 = GHCR dst) and verifies each dst resolves; a dry run pushes nothing,
    # so it must not leave a map that falsely claims images are mirrored.
    [[ "${DRY_RUN}" -eq 1 ]] || : >"${IMAGE_MAP}"
    for entry in "${SOURCES[@]}"; do
        read -r src name <<<"${entry}"
        dst="ghcr.io/${GHCR_ORG}/${name}"
        i=$((i + 1))
        log "[${i}/${total}] ${src} -> ${dst}"
        if [[ "${DRY_RUN}" -eq 1 ]]; then
            continue
        fi
        if crane copy "${src}" "${dst}" >&2; then
            # Print the resulting digest: a manifest that pins by digest needs the new one.
            digest="$(crane digest "${dst}" 2>/dev/null || echo 'unknown')"
            log "  ok  ${dst}@${digest}"
            printf '%s\t%s\t%s\n' "${src}" "${dst}" "${digest}" >>"${IMAGE_MAP}"
        else
            log "  FAILED: ${src}"
            failed=$((failed + 1))
        fi
    done
    log "Done. ${total} attempted, ${failed} failed."
    [[ "${DRY_RUN}" -eq 1 ]] || log "Wrote image map: ${IMAGE_MAP}"
    [[ "${failed}" -eq 0 ]] || exit 1
}

main "$@"
