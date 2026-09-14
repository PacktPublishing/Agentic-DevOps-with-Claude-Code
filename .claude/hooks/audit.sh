#!/usr/bin/env bash
# ABOUTME: Claude Code audit hook. Logs every tool invocation as one structured
# ABOUTME: JSON line with an agent identity label, for per-agent attribution.
set -euo pipefail

# This hook runs on PreToolUse and PostToolUse. It must never break the session,
# so it always exits 0 even when its inputs are unexpected.

LOG_DIR="${CLAUDE_AUDIT_LOG_DIR:-${CLAUDE_PROJECT_DIR:-.}/.claude/audit}"
LOG_FILE="${LOG_DIR}/tool-invocations.jsonl"
AGENT_IDENTITY="${CLAUDE_AGENT_IDENTITY:-claude-code-operator}"

mkdir -p "${LOG_DIR}"

payload="$(cat)"

if ! command -v jq >/dev/null 2>&1; then
  # jq is required to parse the hook payload. Record that it is missing so the
  # gap is visible in the audit trail rather than silently swallowed.
  printf '{"agent_identity":"%s","audit_error":"jq not found on PATH"}\n' \
    "${AGENT_IDENTITY}" >>"${LOG_FILE}"
  exit 0
fi

# Stdin field names verified against the Claude Code hooks docs (June 2026).
# PostToolUse carries the result in tool_response, not tool_output.
printf '%s' "${payload}" | jq -c \
  --arg agent "${AGENT_IDENTITY}" \
  '{
     agent_identity: $agent,
     hook_event_name: .hook_event_name,
     session_id: .session_id,
     cwd: .cwd,
     tool_name: .tool_name,
     tool_input: .tool_input,
     tool_response: .tool_response
   }' >>"${LOG_FILE}" 2>/dev/null || \
  printf '{"agent_identity":"%s","audit_error":"failed to parse payload"}\n' \
    "${AGENT_IDENTITY}" >>"${LOG_FILE}"

exit 0
