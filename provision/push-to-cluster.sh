#!/usr/bin/env bash
# ABOUTME: Pushes your commits to the Git host inside the cluster, which is what ArgoCD reads.
# ABOUTME: This is the GitOps loop: commit locally, push here, watch ArgoCD reconcile.
#
# The in-cluster Gitea is not reachable from your workstation without a port-forward, so this
# opens one, pushes, and closes it. Run it after every commit you want the cluster to pick up.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOCAL_PORT="3000"
BRANCH="${1:-main}"

if ! git -C "${REPO_ROOT}" remote get-url cluster >/dev/null 2>&1; then
    printf 'ERROR: no "cluster" remote. Run ./provision/seed-gitea.sh first.\n' >&2
    exit 2
fi

cleanup() {
    if [[ -n "${PF_PID:-}" ]]; then
        kill "${PF_PID}" 2>/dev/null || true
        wait "${PF_PID}" 2>/dev/null || true
    fi
}
trap cleanup EXIT

kubectl port-forward -n gitea svc/gitea-http "${LOCAL_PORT}:3000" >/dev/null 2>&1 &
PF_PID=$!

for _ in $(seq 1 15); do
    if curl -fsS "http://127.0.0.1:${LOCAL_PORT}/api/v1/version" >/dev/null 2>&1; then break; fi
    sleep 1
done
if ! curl -fsS "http://127.0.0.1:${LOCAL_PORT}/api/v1/version" >/dev/null 2>&1; then
    printf 'ERROR: could not reach Gitea. Check: kubectl get pods -n gitea\n' >&2
    exit 1
fi

printf 'Pushing %s to the cluster...\n' "${BRANCH}"
git -C "${REPO_ROOT}" push cluster "HEAD:refs/heads/${BRANCH}"

printf '\nPushed. ArgoCD polls every few minutes; to see it now:\n'
printf '    kubectl get applications -n argocd\n'
