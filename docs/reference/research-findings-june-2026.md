# Research Findings and Version Pins (June 15, 2026)

This document records the verified current state of every technical source of truth behind this platform, resolved against official sources during the week of June 15, 2026. It is the basis for `versions.lock.md` and for the corrections applied to the specification.

Method: web research against GitHub releases, ArtifactHub, official project docs, the CNCF landscape, AWS docs, Hugging Face model cards, and the Claude Code docs. Training data was not trusted for any version number or maturity claim. Re-resolve once during the week of July 13, 2026, then freeze per the spec.

Maturity claims are stated at the tier the project actually holds. Sandbox is called Sandbox.

---

## 1. Backbone decision (resolved)

- Platform: Amazon EKS. One cluster per student, provisioned and provided live. Up to 300 concurrent.
- Control plane: managed by AWS (not a node you provision).
- Worker nodes: a T3 node group, 2 to 3 workers, vLLM included (t3.2xlarge). Resolved to stay on T3, see the resolution note in section 5.
- vcluster: not used. Removed from the spec.
- Kubernetes version: pin to 1.35 or 1.36 (see section 5).

---

## 2. Master version table

### Foundation: GitOps / Argo (repo `https://argoproj.github.io/argo-helm`)

| Component | App version | Chart | Chart version | Notes |
|---|---|---|---|---|
| Argo CD | v3.4.3 | argo-cd | 9.5.21 | 3.x line, not 2.x. SSA + RBAC breaking changes since 3.0. |
| Argo Workflows | v4.0.6 | argo-workflows | 1.0.15 | v4.0 removed the Python SDK and singular sync primitives. |
| Argo Events | v1.9.10 | argo-events | 2.4.21 | Confirm bundled appVersion before pinning; chart can lag. |
| Argo Rollouts | v1.9.0 | argo-rollouts | 2.41.0 | Dashboard supports Gateway API HTTPRoute. |
| ApplicationSets | (in Argo CD core) | argo-cd | 9.5.21 | Standalone chart retired. CRD now requires server-side apply to install. |
| Roadie ArgoCD plugin | frontend 2.12.5 / backend 4.8.0 | npm, not Helm | n/a | Wire via the new Backstage backend system. Needs service-to-service auth on Backstage 1.24+. |

### Foundation: Developer portal

| Component | Version | Chart | Chart version | Notes |
|---|---|---|---|---|
| Backstage | v1.51.2 (latest patch on the 1.51 line) | backstage | 2.8.1 (repo `https://backstage.github.io/charts`) | Rolling release, not semver. Build a custom image; the chart's built-in image is demo-only. |
| Backstage New Frontend System | default as of 2026 | n/a | n/a | The `--next` flag is gone; the old system is now behind `--legacy`. Tutorials teaching `App.tsx` plugin wiring describe the legacy path. |
| Scaffolder | apiVersion `scaffolder.backstage.io/v1beta3` | n/a | n/a | Templating is Nunjucks, not Handlebars. Register actions via the new backend system extension point. |
| GitHub auth | `@backstage/plugin-auth-backend-module-github-provider` | n/a | n/a | Per-provider backend module. `signIn.resolvers` must be declared explicitly or sign-in fails. |
| Score | spec `score.dev/v1b1` | no chart (CLI binaries) | score-k8s 0.14.0, score-compose 0.41.0 | CNCF Sandbox since July 2024. Not a deployed service. |

### Foundation: Observability

Repo note: the Grafana OSS charts (Loki, Tempo, Grafana) moved to `https://grafana-community.github.io/helm-charts`. The old `grafana/helm-charts` OSS charts are frozen. Point Helm at grafana-community.

| Component | App version | Chart | Chart version | Notes |
|---|---|---|---|---|
| kube-prometheus-stack | operator v0.91.0 | kube-prometheus-stack | 86.2.3 | repo `https://prometheus-community.github.io/helm-charts`. Bundles Grafana 12.4.5, kube-state-metrics 7.4.1, node-exporter 4.55.0. Needs K8s >= 1.25. |
| Prometheus | v3.12.0 | (bundled) | n/a | Prometheus 3.x is the default for operator >= 0.79. |
| Grafana | 13.0.2 | grafana | 12.4.5 (grafana-community) | Chart 12.x ships app 13.x. |
| Alertmanager | v0.33.0 | (bundled) | n/a | Managed by the operator. |
| Loki | 3.7.2 | loki | 17.4.1 (grafana-community) | Simple Scalable (SSD) mode is deprecated. Use monolithic for demos, distributed for production scenarios. |
| Tempo | 2.10.7 | tempo-distributed 2.25.2 / tempo 2.2.3 (grafana-community) | n/a | Default Tempo port changed to 3200 (was 3100). Update datasource and scrape config. |
| OTel Collector | 0.153.0 | opentelemetry-collector | 0.158.1 | repo `https://open-telemetry.github.io/opentelemetry-helm-charts`. |
| OTel Operator | 0.153.0 | opentelemetry-operator | 0.115.0 | Same repo. |

OpenTelemetry is CNCF Graduated (May 11, 2026).

OpenTelemetry GenAI semantic conventions: status is Development, not stable. The conventions moved to a dedicated repo, `open-telemetry/semantic-conventions-genai`, which has no tagged release yet. Present `gen_ai.*` attributes as current but unstable, and note `OTEL_SEMCONV_STABILITY_OPT_IN` where instrumentations support it. Current attribute names (all Development):

| Purpose | Attribute |
|---|---|
| Requested model | `gen_ai.request.model` |
| Responding model | `gen_ai.response.model` |
| Input tokens | `gen_ai.usage.input_tokens` |
| Output tokens | `gen_ai.usage.output_tokens` |
| Operation (chat, embeddings, execute_tool) | `gen_ai.operation.name` |
| Provider | `gen_ai.provider.name` (superseded the older `gen_ai.system`) |
| Tool name | `gen_ai.tool.name` |
| Tool call id | `gen_ai.tool.call.id` |
| Tool type | `gen_ai.tool.type` |

### Foundation: Policy, secrets, scaling, ingress, storage

| Component | App version | Chart | Chart version | Repo | Notes |
|---|---|---|---|---|---|
| Kyverno | v1.18.1 | kyverno | 3.8.1 | kyverno.github.io/kyverno | CNCF Graduated (March 2026). Chart 3.8.1 ships app v1.18.1 (chart and app versions differ). CEL-based policy types (`ValidatingPolicy`, `MutatingPolicy`, etc.) reached GA in 1.17. Legacy JMESPath `ClusterPolicy` deprecated, removal planned v1.20; `validationFailureAction` moved to rule-level `validate.failureAction`. |
| OpenBao | v2.5.5 | openbao | 0.28.4 | openbao.github.io/openbao-helm | Linux Foundation MPL-2.0 fork of Vault (Vault relicensed to BUSL in 2023, no longer OSS). In-cluster secret backend for ESO via the Vault-compatible API, dev mode for the workshop. Replaced Sealed Secrets, dropped as redundant with ESO and because Bitnami retired its chart repo. |
| External Secrets Operator | v2.6.0 | external-secrets | 2.6.0 | charts.external-secrets.io | CNCF Sandbox. v1beta1 API retired; use `external-secrets.io/v1`. Stored v1beta1 objects auto-convert to v1, which causes Argo CD drift unless manifests are migrated. |
| cert-manager | v1.20.2 | cert-manager | v1.20.2 | OCI `oci://quay.io/jetstack/charts/cert-manager` | CNCF Graduated. v1.20 dropped K8s < 1.31. |
| KEDA | 2.20.1 | keda | 2.20.1 | kedacore.github.io/charts | CNCF Graduated. |
| ingress-nginx | RETIRED | do not use | n/a | n/a | End of life March 24, 2026. Repo read-only, no security patches. InGate successor abandoned. Migrate to Gateway API or a maintained controller. |
| MetalLB | 0.16.1 | metallb | 0.16.1 | metallb.github.io/metallb | Pointless on EKS. AWS owns the LB layer. Skip. |
| AWS Load Balancer Controller | v3.4.0 | aws-load-balancer-controller | 3.4.0 | aws.github.io/eks-charts | EKS-native ingress and LB path. ALB for Ingress, NLB for Service type=LoadBalancer, supports Gateway API. Confirm Pod Identity support on the 3.x line before build. |
| AWS EBS CSI driver | v1.61.1 | aws-ebs-csi-driver | 2.61.1 | kubernetes-sigs.github.io/aws-ebs-csi-driver | Needed for PersistentVolumes (Prometheus, Loki, Tempo, Grafana). Also available as an EKS managed add-on. |
| AWS EFS CSI driver | v3.3.0 | aws-efs-csi-driver | 4.3.0 | kubernetes-sigs.github.io/aws-efs-csi-driver | For RWX shared volumes if needed. |

### AI plane

| Component | Version | Install | Foundation / maturity | CRD apiVersion |
|---|---|---|---|---|
| kgateway | v2.3.3 | OCI Helm: `cr.kgateway.dev/kgateway-dev/charts/{kgateway-crds,kgateway}` | CNCF Sandbox since March 2025. Incubation applied, not granted. | `gateway.kgateway.dev/v1alpha1` (Backend, TrafficPolicy, GatewayParameters, ListenerPolicy, GatewayExtension). No RoutePolicy kind. |
| agentgateway | v1.2.1 | standalone YAML config, or OCI Helm `cr.agentgateway.dev/charts/{agentgateway-crds,agentgateway}` | Linux Foundation, Agentic AI Foundation (AAIF), Growth stage. NOT CNCF. Apache-2.0. Written in Rust, not an Envoy wrapper. | CRDs under `agentgateway.dev`. Confirm exact Kind names against the live docs before slides. |
| kagent | v0.9.9 | OCI Helm `ghcr.io/kagent-dev/kagent/helm/{kagent-crds,kagent}` | CNCF Sandbox since May 2025. | `kagent.dev/v1alpha2`. Field is `systemMessage`, nested under `type` + `declarative`. Runs on Google ADK (Python default, Go optional). Kinds: Agent, ModelConfig, RemoteMCPServer/MCPServer, Team. |
| Gateway API | v1.5.1 | `kubectl apply` of standard-install.yaml, no Helm chart for the upstream CRDs | Kubernetes SIG-Network | `gateway.networking.k8s.io/v1` (GatewayClass, Gateway, HTTPRoute, GRPCRoute, TLSRoute, BackendTLSPolicy). TCPRoute/UDPRoute still experimental. |
| Gateway API Inference Extension | v1.5.0 | CRDs via kubectl, Endpoint Picker via Helm `oci://registry.k8s.io/gateway-api-inference-extension/charts/inferencepool` | Kubernetes SIG | `InferencePool` is GA `inference.networking.k8s.io/v1`. `InferenceModel` is gone, replaced by `InferenceObjective` (`inference.networking.x-k8s.io/v1alpha2`). |
| KServe | v0.19.0 | OCI Helm `ghcr.io/kserve/charts/{kserve-crd,kserve-resources}` | CNCF Incubating (entered directly at Incubating from LF AI and Data, Nov 2025). | `serving.kserve.io/v1beta1` (InferenceService); `serving.kserve.io/v1alpha1` (LLMInferenceService, built on the llm-d framework). |
| vLLM | v0.23.0 | CPU image `vllm/vllm-openai-cpu:v0.23.0-x86_64` | PyTorch Foundation, under the Linux Foundation. Apache-2.0. | n/a. Not a standalone KServe ServingRuntime; it backs the Hugging Face runtime and the LLMInferenceService path. |
| llm-d | v0.7.0 | Kustomize (moved off Helm at v0.7) | CNCF Sandbox since March 2026. Backed by Red Hat, Google, IBM, CoreWeave, NVIDIA. Apache-2.0. | Pre-1.0, breaking changes between minors. Do not call it production-ready. |
| LLM Guard | v0.3.16 (May 2025, no newer) | Python library `pip install llm-guard`, optional API image `laiyer/llm-guard-api` | MIT. Protect AI, acquired by Palo Alto Networks (closed July 2025). | n/a. Library, not a deployed service. No Helm chart. Dormant since Sept 2025: a reliability risk worth stating plainly. |
| OpenLLMetry | traceloop-sdk 0.61.0 | Python SDK `pip install traceloop-sdk` (also a JS SDK) | Apache-2.0, NOT MIT. Traceloop. | n/a. Library you add to app code. Emits OTel GenAI conventions. |

### CPU-mode model recommendation

- Primary: `Qwen/Qwen3-1.7B`. Best coherence in the tiny class, around 3.4 GB in bf16, native `Qwen3ForCausalLM` support in current vLLM. Disable thinking mode (`enable_thinking=false`) so CPU latency stays low.
- Backup: `Qwen/Qwen3-0.6B`. Same architecture and code path, about 3x faster, one-line model-id swap.
- Ruled out: SmolLM2-360M and Qwen2.5-0.5B (coherence too weak for an on-screen chat), TinyLlama-1.1B (outclassed by Qwen3-0.6B at half the size), Gemma-3-1b-it (documented vLLM loading bugs, too risky live), SmolLM3 (smallest is 3B, too slow on CPU).

vLLM CPU flags: `--device cpu --dtype bfloat16`, `VLLM_CPU_KVCACHE_SPACE=8` to `16`, `VLLM_CPU_OMP_THREADS_BIND=0-6`. The pod needs the `SYS_NICE` capability or thread binding is blocked by seccomp.

---

## 3. Corrections applied to the build spec

1. Provisioning resolved to EKS, one cluster per student. vcluster removed.
2. ingress-nginx removed (EOL). MetalLB removed (decorative on EKS). AWS Load Balancer Controller is the ingress and LB path. EBS CSI driver added for storage. Component-count impact is a sign-off item (section 5 of the spec).
3. Argo CD is 3.x with server-side-apply and RBAC changes since 3.0. Argo Workflows is 4.x with the Python SDK removed. ApplicationSet CRD requires server-side apply to install.
4. agentgateway is Linux Foundation / AAIF, not CNCF. It is a sibling of kgateway, not its data plane partner.
5. kagent Agent CRD is `kagent.dev/v1alpha2`, field `systemMessage`, runs on Google ADK.
6. OpenLLMetry is Apache-2.0, not MIT.
7. OpenTelemetry is Graduated. Kyverno is Graduated. KServe is Incubating. kgateway, kagent, llm-d, ESO, and Score are Sandbox.
8. OTel GenAI semantic conventions are Development grade. Present as unstable.
9. LLM Guard is dormant and now owned by Palo Alto Networks. Flag the reliability risk.
10. CPU model is Qwen3-1.7B (or 0.6B), not the older trio.
11. vLLM stays on T3 (t3.2xlarge) with model pre-warming and the pre-warmed-request fallback. See the vLLM node resolution in section 5.
12. Claude Code config: docs are at code.claude.com. Six permission modes. PostToolUse hook payload field is `tool_response`, not `tool_output`.

---

## 4. ArgoCD tuning for this scale

Argo CD shards by cluster, not by app. With about 33 apps on one EKS cluster, all apps live in one shard, so controller sharding buys nothing. 33 apps is a small footprint. Relevant knobs:

- `--kubectl-parallelism-limit` (default 20) is adequate for 33 small apps. Set via the chart's `configs.params`.
- Repo-server is the manifest-generation bottleneck. The HA default of 2 replicas is plenty.
- Bake `--server-side --force-conflicts` into bootstrap: the ApplicationSet CRD (3.3+) exceeds the client-side apply annotation limit, and Argo Workflows full-validation CRDs are large.

---

## 5. EKS provisioning notes

vLLM node resolution: research found that T3 burstable throttles under sustained CPU inference and recommended a non-burstable c6i or m6i node. The decision was to stay on T3, for these reasons: T3 is the last Intel x86 instance in the burstable family (t3a is AMD, t4g is ARM Graviton), and the vLLM CPU image is x86-only with immature ARM support, so T3 keeps inference on the supported path; the inference beat is short and bursty rather than a sustained server, and T3 Unlimited (the default) keeps bursting through it; cold-start is handled by pre-warming the model plus the pre-warmed-request fallback. A dedicated compute node and per-cluster Karpenter were both rejected (unnecessary for a bursty demo, and Karpenter adds a controller to 300 clusters plus live node spin-up latency). Benchmark Qwen3-1.7B on t3.2xlarge at the Phase 3 gate; drop to Qwen3-0.6B if it misses. The research finding stands for a sustained-inference production deployment; this is a demo, so it does not apply.

- Supported K8s versions in June 2026: 1.36, 1.35, 1.34, 1.33. 1.33 exits standard support July 29, 2026. Pin to 1.35 or 1.36.
- EKS Auto Mode (GA Dec 2024) manages compute and bundles VPC CNI, CoreDNS, kube-proxy, EBS CSI, and the AWS Load Balancer Controller. It eliminates most per-cluster wiring but hides the LB controller and CSI driver from the GitOps story, which works against the teaching narrative. The chosen direction (managed control plane plus a T3 worker group) implies traditional managed node groups, which is also the higher-fidelity choice for learning GitOps. Recorded as the working plan; Auto Mode noted as an alternative.
- Add-ons as EKS managed add-ons: VPC CNI, CoreDNS, kube-proxy, EBS CSI driver.
- Use EKS Pod Identity (not IRSA) for the AWS Load Balancer Controller. IRSA needs one OIDC provider and a trust policy per cluster, which is 300 of them. Pod Identity uses a generic reusable trust policy.
- Provisioning N identical clusters: terraform-aws-eks v21.20.0 for declarative IaC fleets, or eksctl v0.226.0 for imperative spin-up and teardown. EKS Blueprints is patterns-only since v5 and is not a provisioning framework. Karpenter is v1.13.0; self-managed Karpenter is not worth the per-cluster controller for 300 fixed-shape clusters.

---

## 6. Claude Code config schema (verified June 2026)

Docs are now at `code.claude.com/docs/en/...` (the old `docs.claude.com/en/docs/claude-code` path redirects there).

### CLAUDE.md
Precedence broadest to most specific: managed policy, user (`~/.claude/CLAUDE.md`), project (`./CLAUDE.md` or `./.claude/CLAUDE.md`), `CLAUDE.local.md`, subdirectory `.claude/rules/`. Import syntax `@path`, recursive up to 4 hops. Keep under about 200 lines.

### permissions in settings.json
```json
{
  "permissions": {
    "defaultMode": "default",
    "allow": [
      "Bash(kubectl get:*)",
      "Bash(kubectl describe:*)",
      "Bash(argocd app get:*)",
      "Bash(helm template:*)",
      "Read(./**)"
    ],
    "ask": [
      "Bash(kubectl apply:*)",
      "Bash(kubectl delete:*)",
      "Bash(helm install:*)"
    ],
    "deny": [
      "Read(**/.env)",
      "Edit(.claude/**)"
    ],
    "disableBypassPermissionsMode": "disable"
  }
}
```
- Six modes: `default`, `acceptEdits`, `plan`, `auto`, `dontAsk`, `bypassPermissions`.
- Rule format `Tool(specifier)`. `Bash(kubectl get:*)` and `Bash(kubectl get *)` are equivalent. The space enforces a word boundary.
- Evaluation order: deny, then ask, then allow. First match wins. Specificity does not reorder.
- Compound commands are split on `&&`, `||`, `;`, `|`, `&`, and newline, and each subcommand is checked. Wrappers like `timeout`, `nice`, `nohup` are stripped before matching; `npx`, `docker exec` are not.
- `disableBypassPermissionsMode`, `disableAutoMode`, and `allowManagedPermissionRulesOnly` are managed-settings levers to guarantee a governed demo cannot be escalated.

### hooks
```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          { "type": "command", "command": "${CLAUDE_PROJECT_DIR}/.claude/hooks/audit.sh", "timeout": 600 }
        ]
      }
    ]
  }
}
```
- Event names include `PreToolUse`, `PostToolUse`, `UserPromptSubmit`, `SessionStart`, `SubagentStart`, `SubagentStop`, `Stop`, `SessionEnd`, and many more.
- Stdin payload common fields: `session_id`, `transcript_path`, `cwd`, `permission_mode`, `hook_event_name`. PreToolUse adds `tool_name` and `tool_input`. PostToolUse adds `tool_response` (not `tool_output`).
- For the audit hook that powers the per-agent attribution beat, register PreToolUse and PostToolUse command hooks that read stdin and append JSON lines with `session_id`, `tool_name`, `tool_input`, `tool_response`, `hook_event_name`, `cwd`.
- A PreToolUse hook exiting code 2 blocks the call and takes precedence over allow rules. Deny rules win regardless of hook output.

### subagents
`.claude/agents/<name>.md` with YAML frontmatter (`name`, `description` required). Permission rules can gate them via `Agent(Name)`.

---

## 7. Demo agent model routing and credentials (verified June 2026)

kagent ModelConfig (`kagent.dev/v1alpha2`) supports three relevant providers. The decision is in-cluster vLLM by default, with a real cloud route available for anyone who wants to route outward deliberately.

### In-cluster vLLM (the default)
```yaml
apiVersion: kagent.dev/v1alpha2
kind: ModelConfig
metadata:
  name: vllm-qwen
  namespace: kagent
spec:
  provider: OpenAI
  model: qwen3-1.7b            # must match vLLM --served-model-name
  apiKeySecret: kagent-vllm    # required field; dummy value, vLLM has no --api-key
  apiKeySecretKey: OPENAI_API_KEY
  openAI:
    baseUrl: "http://qwen3-predictor.kserve.svc.cluster.local/v1"  # KServe RawDeployment: <inferenceservice>-predictor
```
vLLM exposes an OpenAI-compatible `/v1/chat/completions`. Set `--served-model-name qwen3-1.7b` so the client model string is clean. No external spend, no external credential.

### Amazon Bedrock via Pod Identity (optional)
```yaml
apiVersion: kagent.dev/v1alpha2
kind: ModelConfig
metadata:
  name: bedrock-native
  namespace: kagent
spec:
  provider: Bedrock
  model: <cheap-bedrock-model-id>
  bedrock:
    region: us-east-1
  deployment:
    serviceAccountName: kagent-bedrock   # bound to an IAM role via Pod Identity, no static key
```
Scope the role to `bedrock:InvokeModel` and `bedrock:InvokeModelWithResponseStream` on specific cheap model ARNs only. AWS Budgets is a soft alert with an 8 to 24 hour data lag, not a real-time hard cap. The preventive IAM model-id allowlist is the actual spend control. Budget Actions can auto-attach a deny policy on threshold, but the lag means spend can accrue first.

### Anthropic API direct, with hard caps (optional)
```yaml
apiVersion: kagent.dev/v1alpha2
kind: ModelConfig
metadata:
  name: claude-model-config
  namespace: kagent
spec:
  provider: Anthropic
  model: <current-claude-model-id>
  apiKeySecret: kagent-anthropic
  apiKeySecretKey: ANTHROPIC_API_KEY
  anthropic: {}
```
Anthropic Console workspace monthly spend limits are a genuine hard stop (the API returns 429 when exceeded). The Usage and Cost Admin API is read-only reporting, not enforcement. For a per-key hard budget, front the key with a LiteLLM proxy virtual key carrying `max_budget` and `budget_duration`; exceeding it is a hard stop (`BudgetExceededError`). Pin and test a known-good LiteLLM version: there are open budget-enforcement bugs, so do not run latest unverified.

### Recommendation
- Default: in-cluster vLLM only. No external credentials, and it scales to any number of clusters with one config.
- Optional: one real cloud route (Bedrock via Pod Identity, or Anthropic behind LiteLLM), scoped and capped. Worth doing deliberately, because the governance lesson lands better when the blast radius is one cluster you own.
- At any scale, do not create one IAM user or one static-key secret per cluster. Use a single scoped IAM role reused across clusters via Pod Identity.

Re-verify at the freeze: kagent v0.9.9 exact field names against the tagged API reference, whether kagent documents the Pod Identity association vs the IRSA annotation, the current Anthropic model id for the demo, and a LiteLLM version that passes a live budget-enforcement test.

## 8. Items to re-verify before the freeze (week of July 13)

- agentgateway exact Kubernetes CRD Kind names and apiVersions.
- AWS Load Balancer Controller Pod Identity support on the 3.x chart line.
- Chart versions for all fast-moving AI-plane projects (they publish monthly).
- Backstage exact patch version on the then-current line.
- vLLM CPU performance of Qwen3-1.7B on the chosen worker instance, against the latency gate.
