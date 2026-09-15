#!/usr/bin/env bash
# ABOUTME: Vendors every Helm chart the platform Applications reference into
# ABOUTME: charts-vendor/ as pinned .tgz files, so nothing waits on the network live.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
readonly SCRIPT_DIR REPO_ROOT
readonly VENDOR_DIR="${REPO_ROOT}/charts-vendor"
# The reference build moved from platform/ to solution/platform/ when the student's empty
# platform/ was split out. This path did not move with it, so `find` matched nothing and the
# script vendored zero charts while exiting successfully. Anything already in charts-vendor/
# predates the move, which is why the breakage was invisible.
readonly PLATFORM_DIR="${REPO_ROOT}/solution/platform"

log() { printf '%s\n' "$*" >&2; }

command -v helm >/dev/null 2>&1 || { log "helm not found"; exit 1; }
mkdir -p "${VENDOR_DIR}"

# Emit "repoURL<TAB>chart<TAB>targetRevision" for every Application with a Helm chart.
extract_charts() {
    local f repo chart rev
    while IFS= read -r f; do
        # || true: pipefail would otherwise make a no-match grep fail the assignment
        # (raw-manifest apps have no chart line) and set -e would abort extraction.
        chart="$(grep -E "^[[:space:]]*chart:" "${f}" | head -1 | sed -E 's/.*chart:[[:space:]]*//' || true)"
        [[ -n "${chart}" ]] || continue
        repo="$(grep -E "repoURL:" "${f}" | head -1 | sed -E 's/.*repoURL:[[:space:]]*//' || true)"
        rev="$(grep -E "targetRevision:" "${f}" | head -1 \
               | sed -E 's/.*targetRevision:[[:space:]]*//; s/"//g' || true)"
        printf '%s\t%s\t%s\n' "${repo}" "${chart}" "${rev}"
    done < <(find "${PLATFORM_DIR}" -name application.yaml)
}

pull_one() {
    local repo="$1" chart="$2" rev="$3"
    if [[ "${repo}" == http* ]]; then
        helm pull "${chart}" --repo "${repo}" --version "${rev}" --destination "${VENDOR_DIR}"
    else
        # No scheme in repoURL means an OCI registry path.
        helm pull "oci://${repo}/${chart}" --version "${rev}" --destination "${VENDOR_DIR}"
    fi
}

main() {
    [[ -d "${PLATFORM_DIR}" ]] || {
        log "platform directory not found: ${PLATFORM_DIR}"
        log "If the reference build has moved again, update PLATFORM_DIR."
        exit 1
    }
    local rows; mapfile -t rows < <(extract_charts | sort -u)
    local total="${#rows[@]}" i=0 failed=0 repo chart rev
    # Vendoring nothing is a failure, not a no-op. Exiting 0 having done nothing is how this
    # script hid a broken path for as long as it did.
    [[ "${total}" -gt 0 ]] || {
        log "found no Applications with a chart under ${PLATFORM_DIR}"
        log "That is a bug in this script or a moved tree, not an empty platform."
        exit 1
    }
    log "Vendoring ${total} charts into ${VENDOR_DIR#"${REPO_ROOT}"/}"
    for row in "${rows[@]}"; do
        IFS=$'\t' read -r repo chart rev <<<"${row}"
        i=$((i + 1))
        log "[${i}/${total}] ${chart} ${rev}"
        # Attempt every chart; a single failure must not hide the rest.
        if ! pull_one "${repo}" "${chart}" "${rev}"; then
            log "  FAILED: ${chart} ${rev} from ${repo}"
            failed=$((failed + 1))
        fi
    done
    log "Done. Vendored $((total - failed))/${total}:"
    ls -1 "${VENDOR_DIR}"/*.tgz 2>/dev/null | sed "s#${REPO_ROOT}/##" >&2 || true
    [[ "${failed}" -eq 0 ]] || { log "${failed} chart(s) failed to vendor"; exit 1; }
}

main "$@"
