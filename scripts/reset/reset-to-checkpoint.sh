#!/usr/bin/env bash
# ABOUTME: Rolls the platform back to a checkpoint tag by re-pointing the root
# ABOUTME: App-of-Apps at that revision and force-syncing with prune.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
readonly SCRIPT_DIR REPO_ROOT
readonly ROOT_APP="platform-foundation"

KUBECONFIG_FILE="${KUBECONFIG_FILE:-}"
EXPECTED_CONTEXT="${EXPECTED_CONTEXT:-}"

log() { printf '%s\n' "$*" >&2; }

usage() {
    cat >&2 <<EOF
Usage: KUBECONFIG_FILE=<path> EXPECTED_CONTEXT=<substr> ${0##*/} <checkpoint-tag>

Re-points the root App-of-Apps ('${ROOT_APP}') at the given checkpoint tag and triggers
a sync with prune, so the foundation reconciles to that pinned known-good revision and any
cluster drift is removed. The checkpoint tags are immutable good revisions, not partial
module snapshots, so this recovers a broken or drifted foundation to a verified state.

  checkpoint-tag   e.g. checkpoint/module-1-end

Preconditions: the tag exists and is pushed to the Git remote ArgoCD reads; the root
App-of-Apps is installed. Uses an explicit kubeconfig only, never the shared default.
EOF
    exit 2
}

kc() { kubectl --kubeconfig "${KUBECONFIG_FILE}" "$@"; }

guard_context() {
    local ctx; ctx="$(kc config current-context 2>/dev/null || true)"
    if [[ "${ctx}" != *"${EXPECTED_CONTEXT}"* ]]; then
        log "ABORT: context '${ctx}' does not match expected '${EXPECTED_CONTEXT}'"
        exit 1
    fi
    log "context confirmed: ${ctx}"
}

main() {
    local checkpoint="${1:-}"
    [[ -n "${checkpoint}" && -n "${KUBECONFIG_FILE}" && -n "${EXPECTED_CONTEXT}" ]] || usage
    [[ -f "${KUBECONFIG_FILE}" ]] || { log "kubeconfig not found: ${KUBECONFIG_FILE}"; exit 1; }
    command -v kubectl >/dev/null 2>&1 || { log "kubectl not found"; exit 1; }

    git -C "${REPO_ROOT}" rev-parse -q --verify "refs/tags/${checkpoint}" >/dev/null 2>&1 \
        || { log "unknown checkpoint tag: ${checkpoint}"; exit 1; }

    guard_context

    kc get application "${ROOT_APP}" -n argocd >/dev/null 2>&1 \
        || { log "root App-of-Apps '${ROOT_APP}' not found in argocd"; exit 1; }

    log "re-pointing ${ROOT_APP} at ${checkpoint}"
    kc patch application "${ROOT_APP}" -n argocd --type merge \
        -p "{\"spec\":{\"source\":{\"targetRevision\":\"${checkpoint}\"}}}" >&2

    log "triggering sync with prune"
    kc patch application "${ROOT_APP}" -n argocd --type merge -p \
        '{"operation":{"initiatedBy":{"username":"reset"},"sync":{"prune":true,"syncStrategy":{"hook":{}}}}}' >&2

    log "reset to ${checkpoint} requested. Watch convergence with:"
    log "  kubectl --kubeconfig ${KUBECONFIG_FILE} get applications -n argocd -w"
}

main "$@"
