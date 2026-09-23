#!/usr/bin/env bash
# ABOUTME: Pushes the Claude Code audit JSONL to Loki so the B17 attribution
# ABOUTME: queries and the AI Plane dashboard panel return data.
set -euo pipefail

# The audit hook (.claude/hooks/audit.sh) writes one JSON line per tool invocation to a
# local file. Nothing ships those lines to Loki on its own. This script reads the file
# and pushes each line to Loki's push API under the stream label job="claude-audit", with
# a second label agent_identity so per-agent attribution works. Audit lines carry no
# timestamp, so ingestion time is stamped here, incremented per line to stay strictly
# increasing within each stream (Loki rejects out-of-order lines in a stream).

readonly JOB_LABEL="claude-audit"

AUDIT_FILE="${CLAUDE_AUDIT_FILE:-${CLAUDE_PROJECT_DIR:-.}/.claude/audit/tool-invocations.jsonl}"
LOKI_URL="${LOKI_URL:-}"
KUBECONFIG_FILE="${KUBECONFIG_FILE:-}"
EXPECTED_CONTEXT="${EXPECTED_CONTEXT:-}"
LOKI_SVC="${LOKI_SVC:-loki}"
LOKI_NS="${LOKI_NS:-observability}"
LOKI_PORT="${LOKI_PORT:-3100}"
LOCAL_PORT="${LOCAL_PORT:-3100}"

PF_PID=""
TMP_PAYLOAD=""

log() { printf '%s\n' "$*" >&2; }

usage() {
    cat >&2 <<EOF
Usage:
  Direct (already reachable, e.g. in-cluster or pre-forwarded):
    LOKI_URL=http://127.0.0.1:3100 ${0##*/}

  Via a guarded port-forward to the cluster you provisioned this session:
    KUBECONFIG_FILE=<path> EXPECTED_CONTEXT=<substr> ${0##*/}

Reads the audit JSONL (default \$CLAUDE_PROJECT_DIR/.claude/audit/tool-invocations.jsonl,
override with CLAUDE_AUDIT_FILE) and pushes every line to Loki under job="${JOB_LABEL}"
with an agent_identity label. Requires jq and curl. kubectl is required only for the
port-forward path.
EOF
    exit 2
}

cleanup() {
    [[ -n "${PF_PID}" ]] && kill "${PF_PID}" 2>/dev/null || true
    [[ -n "${TMP_PAYLOAD}" && -f "${TMP_PAYLOAD}" ]] && rm -f "${TMP_PAYLOAD}" || true
}
trap cleanup EXIT

require_tools() {
    command -v jq >/dev/null 2>&1 || { log "jq not found on PATH"; exit 1; }
    command -v curl >/dev/null 2>&1 || { log "curl not found on PATH"; exit 1; }
}

guard_context() {
    local ctx
    ctx="$(kubectl --kubeconfig "${KUBECONFIG_FILE}" config current-context 2>/dev/null || true)"
    [[ "${ctx}" == *"${EXPECTED_CONTEXT}"* ]] || {
        log "ABORT: context '${ctx}' does not match expected '${EXPECTED_CONTEXT}'"; exit 1; }
}

start_port_forward() {
    command -v kubectl >/dev/null 2>&1 || { log "kubectl not found (needed for port-forward)"; exit 1; }
    [[ -f "${KUBECONFIG_FILE}" ]] || { log "kubeconfig not found: ${KUBECONFIG_FILE}"; exit 1; }
    guard_context
    log "Port-forwarding svc/${LOKI_SVC} in ${LOKI_NS} to 127.0.0.1:${LOCAL_PORT} ..."
    kubectl --kubeconfig "${KUBECONFIG_FILE}" -n "${LOKI_NS}" \
        port-forward "svc/${LOKI_SVC}" "${LOCAL_PORT}:${LOKI_PORT}" >/dev/null 2>&1 &
    PF_PID=$!
    # Wait for the local port to answer rather than sleeping a fixed interval.
    local tries=0
    until curl -sS -m 2 -o /dev/null "http://127.0.0.1:${LOCAL_PORT}/ready" 2>/dev/null; do
        tries=$((tries + 1))
        [[ "${tries}" -ge 30 ]] && { log "port-forward did not become ready"; exit 1; }
        kill -0 "${PF_PID}" 2>/dev/null || { log "port-forward process exited early"; exit 1; }
        sleep 1
    done
    LOKI_URL="http://127.0.0.1:${LOCAL_PORT}"
    log "Port-forward ready."
}

build_payload() {
    # Stamp a base epoch-seconds value once, then append a 9-digit zero-padded per-line
    # index as the nanosecond part. Kept as strings throughout so 19-digit nanosecond
    # timestamps never lose precision to jq's double-based numbers.
    local base_s
    base_s="$(date +%s)"
    TMP_PAYLOAD="$(mktemp -p . ship-audit.XXXXXX.json)"
    jq -s \
        --arg job "${JOB_LABEL}" \
        --arg base "${base_s}" \
        '
        [ to_entries[]
          | {
              line: (.value | @json),
              agent: ((.value.agent_identity) // "unknown"),
              ts: ($base + ((.key + 1000000000) | tostring)[1:])
            }
        ]
        | group_by(.agent)
        | { streams: [ .[] | {
              stream: { job: $job, agent_identity: .[0].agent },
              values: [ .[] | [ .ts, .line ] ]
            } ] }
        ' "${AUDIT_FILE}" >"${TMP_PAYLOAD}"
}

push_payload() {
    local code
    code="$(curl -sS -m 30 -o /dev/null -w '%{http_code}' \
        -H 'Content-Type: application/json' \
        -X POST "${LOKI_URL}/loki/api/v1/push" \
        --data-binary "@${TMP_PAYLOAD}" || true)"
    if [[ "${code}" == "204" ]]; then
        log "Pushed ${LINE_COUNT} line(s) to Loki (${LOKI_URL}), HTTP ${code}."
    else
        log "Push failed: HTTP ${code:-none} from ${LOKI_URL}/loki/api/v1/push"
        exit 1
    fi
}

main() {
    require_tools
    [[ -f "${AUDIT_FILE}" ]] || { log "audit file not found: ${AUDIT_FILE}"; exit 1; }

    LINE_COUNT="$(grep -c . "${AUDIT_FILE}" || true)"
    [[ "${LINE_COUNT}" -gt 0 ]] || { log "audit file is empty: ${AUDIT_FILE}"; exit 0; }
    log "Read ${LINE_COUNT} audit line(s) from ${AUDIT_FILE}."

    if [[ -z "${LOKI_URL}" ]]; then
        [[ -n "${KUBECONFIG_FILE}" && -n "${EXPECTED_CONTEXT}" ]] || usage
        start_port_forward
    fi

    build_payload
    push_payload
}

main "$@"
