<!-- ABOUTME: LogQL queries for the per-agent attribution demo and their label contract. -->
<!-- ABOUTME: The queries only return data once the audit stream is shipped to Loki. -->

# Attribution queries

`loki-agent-attribution.logql` holds the LogQL for the B17 per-agent
attribution demo. The queries answer one question: which agent identity took
which action, and how many.

## Label contract

Every query keys on two things:

- The stream label `job="claude-audit"`, applied by the shipper when it pushes
  lines to Loki.
- A JSON field `agent_identity` on every line, written by the audit hook at
  `.claude/hooks/audit.sh`. Its default value is `claude-code-operator`; set
  `CLAUDE_AGENT_IDENTITY` before a session to attribute actions to a different
  identity.

The hook writes each tool invocation to
`.claude/audit/tool-invocations.jsonl` as one JSON line. The fields are
`agent_identity`, `hook_event_name`, `session_id`, `cwd`, `tool_name`,
`tool_input`, `tool_response`.

## Getting data into Loki

The audit hook writes to a local file. Nothing ships it to Loki on its own.
`scripts/ship-audit-to-loki.sh` reads the JSONL file and pushes each line to
Loki's push API with the `job="claude-audit"` stream label, so these queries
and the AI-plane dashboard panel return data. Run the shipper before the
attribution demo, or leave it tailing during the session.

## The queries

1. **Per-agent audit trail** (`line_format`): one readable line per invocation,
   agent then event then tool. Good for the logs panel and for reading live.
2. **Actions per agent identity (5m)**: the attribution metric. This is the
   exact query the `Actions per agent identity` panel on the AI Plane dashboard
   runs.
3. **Single identity**: filters to `claude-code-operator` to show one actor in
   isolation.
4. **Audit gaps**: surfaces lines where the hook recorded an `audit_error`
   (missing jq, unparseable payload) so a gap is visible rather than silent.
