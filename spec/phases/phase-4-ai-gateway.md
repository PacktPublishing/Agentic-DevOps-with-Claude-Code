# Phase 4: AI gateway plane (chapter 6)

**Goal:** The AI gateway plane installed and the AI-plane policies defined in audit mode, so the AI plane is governed from birth.

**Inputs:** The foundation complete (a working IDP). Gateway API CRDs are a prerequisite for the gateways.

**Outputs:**
- Gateway API standard CRDs (v1.5.1) applied with server-side apply
- kgateway (v2.3.4) installed from its OCI charts (kgateway-crds then kgateway) into kgateway-system
- agentgateway (v1.3.0) installed from its own native OCI charts (agentgateway-crds then agentgateway) into agentgateway-system, with client-certificate mTLS, the prompt guardrail, and audit access logging configured at runtime
- The AI-plane Kyverno policies defined in audit mode: require an LLM Guard policy reference on agents, image allowlist for AI namespaces, require OTel annotations, deny agent-namespace egress to LLM endpoints that bypass agentgateway

**Test criteria (tests/test_phase_4_ai_gateway.py):**
- Gateway API CRDs are established at v1 (GatewayClass, Gateway, HTTPRoute)
- kgateway and agentgateway pods are Ready in their namespaces
- A Gateway resource reconciles and is programmed
- The AI-plane Kyverno policies exist in Audit mode (not Enforce) and report, not block

**Completion promise:** `<promise>PHASE4_DONE</promise>`

**Key decisions:**
- agentgateway is a Linux Foundation / Agentic AI Foundation project, not CNCF, and a sibling of kgateway, not its data plane. Install agentgateway from its native charts (cr.agentgateway.dev), not the legacy kgateway-hosted 2.x charts.
- kgateway is CNCF Sandbox; its CRDs are `gateway.kgateway.dev/v1alpha1`. Lock to the stable patch, no alpha.
- Pick one owner for the Gateway API CRDs (the upstream manifest or a controller), not both.
- Policies start in Audit so the AI plane lands governed; Phase 8 flips them to Enforce.

**Stop here.** Output the completion promise and wait. Read the routing config that mediates LLM, MCP and A2A traffic, and note that the policies are already watching in Audit mode before anything enforces.
