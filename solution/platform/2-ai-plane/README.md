# 2-ai-plane: the AI plane

Built in Module 2, the centerpiece. One directory per component, same shape as the foundation: an ArgoCD `application.yaml` plus any raw manifests under `manifests/`. The `*-crds` directories pre-install CRDs in an earlier sync wave so the controllers that need them reconcile cleanly.

What lands here: kgateway and agentgateway (the agentic data plane), kagent (declarative agents), LLM Guard (prompt-injection defense), OpenLLMetry with OTel GenAI conventions, KServe serving the CPU model with vLLM, and llm-d. The `demo-agent` and `mcp-server` directories carry the live demo workloads.

Applied via the AI-plane App-of-Apps at `../0-bootstrap/ai-plane-app.yaml`.
