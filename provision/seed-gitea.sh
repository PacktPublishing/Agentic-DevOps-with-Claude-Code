#!/usr/bin/env bash
# ABOUTME: Installs the in-cluster Git host, seeds it with your platform tree, and starts ArgoCD.
# ABOUTME: Breaks the bootstrap cycle: every other Application is read from Gitea, but Gitea is not.
#
# Twenty-two Applications in this platform source their manifests from a Gitea running inside the
# cluster. Gitea's own Application does not: it pulls its chart from dl.gitea.com. So the cycle
# breaks by applying that one Application directly, seeding the repo, and only then handing ArgoCD
# the root App-of-Apps.
#
# The cluster becomes self-contained after this: ArgoCD reads from a Git host inside it, you push
# to that host, and nothing in the reconcile path leaves the cluster. Your local clone stays the
# source of truth, because the in-cluster copy dies with the cluster.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GITEA_APP="${REPO_ROOT}/platform/1-foundation/gitea/application.yaml"
ROOT_APP="${REPO_ROOT}/platform/0-bootstrap/root-app.yaml"
ORG="platform"
REPO="packt-agentic-devops"
LOCAL_PORT="3000"

for f in "${GITEA_APP}" "${ROOT_APP}"; do
    if [[ ! -f "${f}" ]]; then
        printf 'ERROR: %s not found.\n' "${f}" >&2
        printf 'Create your working copy first:  cp -a solution/platform/. platform/\n' >&2
        exit 2
    fi
done

if grep -rq 'REPLACE_WITH_' "${REPO_ROOT}/platform" 2>/dev/null; then
    printf 'ERROR: platform/ still has unsubstituted placeholders. Run provision/cluster-facts.sh first.\n' >&2
    exit 2
fi

cleanup() {
    if [[ -n "${PF_PID:-}" ]]; then
        kill "${PF_PID}" 2>/dev/null || true
        wait "${PF_PID}" 2>/dev/null || true
    fi
}
trap cleanup EXIT

# --- 1. Install Gitea --------------------------------------------------------------------------
# Applied directly rather than through the App-of-Apps, because the App-of-Apps is read from the
# thing this installs. ArgoCD adopts this same object when root-app syncs later, so there is no
# second copy of the values to drift.
printf '[1/5] Installing Gitea...\n'
kubectl apply -n argocd -f "${GITEA_APP}"

# --- 2. Derive the seed credentials from the chart values ---------------------------------------
# gitea-config/manifests/seed-job.yaml reads gitea-seed-creds. Deriving it from the Application
# that sets the admin account means the two cannot disagree. A second hand-written copy is the
# credentials-that-drift defect this repo keeps rediscovering.
printf '[2/5] Deriving gitea-seed-creds from the chart values...\n'
ADMIN_USER="$(grep -A4 '^ *admin:' "${GITEA_APP}" | sed -n 's/^ *username: *//p' | head -1)"
ADMIN_PASS="$(grep -A4 '^ *admin:' "${GITEA_APP}" | sed -n 's/^ *password: *"\?\([^"]*\)"\?/\1/p' | head -1)"
if [[ -z "${ADMIN_USER}" || -z "${ADMIN_PASS}" ]]; then
    printf 'ERROR: could not read the Gitea admin account out of %s\n' "${GITEA_APP}" >&2
    exit 1
fi
kubectl create namespace gitea --dry-run=client -o yaml | kubectl apply -f - >/dev/null
kubectl create secret generic gitea-seed-creds \
    --namespace gitea \
    --from-literal=username="${ADMIN_USER}" \
    --from-literal=password="${ADMIN_PASS}" \
    --dry-run=client -o yaml | kubectl apply -f - >/dev/null

# --- 3. Wait for it to answer -------------------------------------------------------------------
printf '[3/5] Waiting for Gitea to become ready (up to 5 minutes)...\n'
if ! kubectl wait --for=condition=available --timeout=300s \
        -n gitea deployment/gitea >/dev/null 2>&1; then
    printf 'ERROR: Gitea did not become available. Check: kubectl get pods -n gitea\n' >&2
    exit 1
fi

kubectl port-forward -n gitea svc/gitea-http "${LOCAL_PORT}:3000" >/dev/null 2>&1 &
PF_PID=$!
GITEA="http://127.0.0.1:${LOCAL_PORT}"
for _ in $(seq 1 30); do
    if curl -fsS "${GITEA}/api/v1/version" >/dev/null 2>&1; then break; fi
    sleep 2
done
if ! curl -fsS "${GITEA}/api/v1/version" >/dev/null 2>&1; then
    printf 'ERROR: Gitea is running but its API did not answer on the port-forward.\n' >&2
    exit 1
fi

# --- 4. Create the org and repo, both public ----------------------------------------------------
# Public so ArgoCD reads them anonymously and needs no repository credential.
printf '[4/5] Creating %s/%s and pushing your platform tree...\n' "${ORG}" "${REPO}"
curl -sS -u "${ADMIN_USER}:${ADMIN_PASS}" -X POST "${GITEA}/api/v1/orgs" \
    -H 'Content-Type: application/json' \
    -d "{\"username\":\"${ORG}\",\"visibility\":\"public\"}" -o /dev/null || true
curl -sS -u "${ADMIN_USER}:${ADMIN_PASS}" -X POST "${GITEA}/api/v1/orgs/${ORG}/repos" \
    -H 'Content-Type: application/json' \
    -d "{\"name\":\"${REPO}\",\"private\":false,\"auto_init\":false}" -o /dev/null || true

REMOTE="http://${ADMIN_USER}:${ADMIN_PASS}@127.0.0.1:${LOCAL_PORT}/${ORG}/${REPO}.git"
git -C "${REPO_ROOT}" remote remove cluster 2>/dev/null || true
git -C "${REPO_ROOT}" remote add cluster "${REMOTE}"
git -C "${REPO_ROOT}" push --quiet cluster HEAD:refs/heads/main --force

# --- 5. Hand ArgoCD the root App-of-Apps --------------------------------------------------------
printf '[5/5] Applying the root App-of-Apps...\n'
kubectl apply -n argocd -f "${ROOT_APP}"

cat <<EOF

Gitea is seeded and ArgoCD is reconciling from it.

Watch it converge:
    kubectl get applications -n argocd -w

After every commit, push to the cluster with:
    ./provision/push-to-cluster.sh

Your local clone is the source of truth. The copy inside the cluster dies with the cluster.
EOF
