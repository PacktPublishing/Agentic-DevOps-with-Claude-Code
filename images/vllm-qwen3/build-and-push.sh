#!/usr/bin/env bash
# ABOUTME: Builds the Qwen3-baked vLLM CPU image and pushes it to GHCR. Run once before
# ABOUTME: the event; the InferenceService then loads the model from disk, not HuggingFace.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GHCR_ORG="${GHCR_ORG:-}"
TAG="${TAG:-v0.23.0-qwen3-1.7b}"

[[ -n "${GHCR_ORG}" ]] || { echo "Usage: GHCR_ORG=<org> [TAG=...] ${0##*/}" >&2; exit 2; }
command -v docker >/dev/null 2>&1 || { echo "docker not found / not accessible" >&2; exit 1; }

readonly IMAGE="ghcr.io/${GHCR_ORG}/vllm-qwen3:${TAG}"
echo "building ${IMAGE}" >&2
docker build -t "${IMAGE}" "${SCRIPT_DIR}"
echo "pushing ${IMAGE}" >&2
docker push "${IMAGE}"
echo "${IMAGE}"
