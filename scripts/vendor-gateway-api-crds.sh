#!/usr/bin/env bash
# ABOUTME: Vendors the Gateway API standard-channel CRDs at the pinned tag, so ArgoCD never fetches
# ABOUTME: them from GitHub at sync time. The chart equivalent is vendor-charts.sh.
#
# These are not a Helm chart, so vendor-charts.sh does not cover them, and they were the one
# remaining live network dependency in a platform that vendors everything else. The AI plane cannot
# start without them, which makes them the worst thing to leave behind a GitHub fetch.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
readonly SCRIPT_DIR REPO_ROOT

# Keep in step with the gateway-api pin in components.yaml. Passed as $1 to vendor a different tag.
VERSION="${1:-v1.5.1}"
readonly DEST="${REPO_ROOT}/solution/platform/2-ai-plane/gateway-api/manifests"
readonly BASE="https://raw.githubusercontent.com/kubernetes-sigs/gateway-api/${VERSION}/config/crd/standard"

# The standard channel. Experimental carries frontendValidation (client-cert mTLS) and is
# deliberately not used; see the tracking issue before switching channels.
readonly CRDS=(
    gateway.networking.k8s.io_gatewayclasses.yaml
    gateway.networking.k8s.io_gateways.yaml
    gateway.networking.k8s.io_httproutes.yaml
    gateway.networking.k8s.io_grpcroutes.yaml
    gateway.networking.k8s.io_referencegrants.yaml
)

log() { printf '%s\n' "$*" >&2; }

mkdir -p "${DEST}"
log "Vendoring Gateway API ${VERSION} standard-channel CRDs into ${DEST#"${REPO_ROOT}"/}"

failed=0
for crd in "${CRDS[@]}"; do
    if curl -fsSL "${BASE}/${crd}" -o "${DEST}/${crd}.tmp"; then
        # Verify before replacing: a 404 page or a redirect would otherwise be written over a good
        # CRD and only fail later, on a cluster, as a missing type.
        if grep -q "^kind: CustomResourceDefinition" "${DEST}/${crd}.tmp"; then
            mv "${DEST}/${crd}.tmp" "${DEST}/${crd}"
            log "  ok: ${crd}"
        else
            rm -f "${DEST}/${crd}.tmp"
            log "  FAILED: ${crd} downloaded but is not a CRD"
            failed=$((failed + 1))
        fi
    else
        rm -f "${DEST}/${crd}.tmp"
        log "  FAILED: ${crd} not found at ${VERSION}"
        failed=$((failed + 1))
    fi
done

[[ "${failed}" -eq 0 ]] || { log "${failed} CRD(s) failed to vendor"; exit 1; }
log "Done. Update the gateway-api pin in components.yaml if the version changed."
