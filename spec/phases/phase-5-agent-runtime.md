# Phase 5: Agent runtime and safety (chapter 7)

**Goal:** kagent running, a demo Agent declared and reconciled by GitOps, calling an MCP server through agentgateway, with LLM Guard blocking a prompt-injection attempt and OpenLLMetry wired.

**Inputs:** Phase 4 complete (gateways up, AI policies in audit). The MCP demo server deployed: the MCP everything server over Streamable HTTP (image `mcp/everything`, mirrored to GHCR), behind a Service and routed through agentgateway.

**Outputs:**
- kagent (v0.9.9) installed from its OCI charts (kagent-crds then kagent) into the kagent namespace
- A demo Agent CRD written live: `kagent.dev/v1alpha2`, `kind: Agent`, `spec.type: Declarative`, `spec.declarative.systemMessage`, committed to Git and reconciled by ArgoCD
- A ModelConfig pointing at the in-cluster vLLM OpenAI-compatible endpoint (no external key, no external spend); served in Phase 6, so the route is declared here and exercised after
- LLM Guard (pinned 0.3.16) deployed as the input/output filter; the prompt-injection fixture is blocked and the block appears in the agentgateway audit log
- OpenLLMetry (traceloop-sdk 0.61.0) instrumentation emitting OTel GenAI conventions to the collector

**Test criteria (tests/test_phase_5_agent_runtime.py):**
- The kagent Agent CRD is `kagent.dev/v1alpha2` and the demo Agent is reconciled and Ready
- The agent reaches an MCP server through agentgateway and an audit log entry is recorded
- The prompt-injection fixture is blocked by LLM Guard and the blocked request appears in the audit log
- OpenLLMetry spans with `gen_ai.*` attributes reach the collector

**Completion promise:** `<promise>PHASE5_DONE</promise>`

**Key decisions:**
- The Agent CRD is `kagent.dev/v1alpha2`, field `systemMessage` under `spec.declarative`, runtime Google ADK. Never write v1alpha1 or `systemPrompt`. Preflight that the live CRD shows v1alpha2.
- LLM Guard is effectively frozen (0.3.16, no releases since mid-2025 post-acquisition); pin it, vendor the config, mirror the multi-GB image to GHCR and pre-pull. The injection block is deterministic and reset-restorable.
- OpenLLMetry is Apache-2.0 (not MIT); it emits GenAI conventions that are Development grade. Set `OTEL_SEMCONV_STABILITY_OPT_IN=gen_ai_latest_experimental`.
- The agent calls only the in-cluster vLLM.
- MCP wiring: the agent references the MCP server via `spec.tools[]` `type: McpServer` with `mcpServer.kind: RemoteMCPServer` (`kagent.dev/v1alpha2`, points at the agentgateway URL, `protocol: STREAMABLE_HTTP`, path `/mcp`). Note the kmcp split: a server kmcp deploys in-cluster is `MCPServer` (`kagent.dev/v1alpha1`); a server reached by URL is `RemoteMCPServer` (`kagent.dev/v1alpha2`). The agentgateway-in-front URL mapping is the thinnest-documented area; validate it live before the demo. MCP spec revision is 2025-11-25; do not use the deprecated HTTP+SSE transport.

**Stop here.** Output the completion promise and wait. Read the audit log for both: the MCP call that succeeded, and the injection that was refused.
