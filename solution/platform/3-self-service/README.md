# 3-self-service: the self-service golden path

Built in Module 3. This plane turns the platform into a product: a developer requests an agent through Backstage and the platform delivers it, governed and audited.

- `agent-service/`: the Backstage scaffolder template. A form (agent name, purpose, model route, allowed MCP tools) generates a repo with a kagent Agent CRD, an agentgateway route, an LLM Guard policy reference, and OTel defaults.
- `applicationset.yaml`: watches the in-cluster Gitea for those generated repos and auto-creates an ArgoCD Application for each, so the new agent deploys through the same GitOps path as everything else.

Applied via the self-service App-of-Apps at `../0-bootstrap/self-service-app.yaml`.
