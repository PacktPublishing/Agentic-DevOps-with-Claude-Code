# Prompt Library

The prompts that drive each phase of the build, in the order you reach them. Use them as written
or as a starting point. Each one says what a good response looks like, what commonly goes wrong,
and what to do about it.

Chapter numbers map to phases as chapter = phase + 2. The spec for each phase is in
`spec/phases/`, and the test that proves it landed is named in the spec.

## Two rules the prompts assume

**GitOps.** Your agent writes and commits manifests to `platform/`, pushes to the in-cluster Git
host, and ArgoCD syncs them. It does not run mutating `kubectl` directly. There are two sanctioned
exceptions: the bootstrap, which installs ArgoCD and seeds the Git host before there is anything to
sync from, and the Kyverno denial in chapter 10, which is the point of that exercise.
`.claude/settings.json` enforces this. When your agent reaches for a mutating verb, it stops and
asks you to approve. That pause is the permission policy working, not an obstacle.

**Cluster access.** Your kubeconfig is already cluster-admin, because
`enable_cluster_creator_admin_permissions` in `provision/main.tf` gives an access entry to whoever
ran `terraform apply`. So the agent never needs to grant itself Kubernetes or AWS access.

If a run opens with `eks:CreateAccessEntry`, `aws eks create-access-entry`, or any other attempt to
obtain permission before installing anything, stop it. Nothing in the build needs it, and an agent
that starts by reasoning about its own IAM will stall before it has installed a single component.
It is the most common way a run gets stuck at the first phase. If a step appears to need more
access, it does not; reconcile through ArgoCD as above.

## Format

Each entry gives the prompt, what a good response looks like, what commonly goes wrong, and what to
do about it.

---

## Chapter 3: the GitOps foundation

### Read the component manifest and explain the build

**Prompt:**
> Read `components.yaml` and `platform/0-bootstrap/root-app.yaml`. In a few sentences, explain
> how the App-of-Apps pattern is going to deploy this platform: what the root Application
> points at, how the per-component Applications are discovered, and how sync waves order the
> rollout. Do not apply anything yet.

**A good response** reads both files and explains that `platform-foundation` points ArgoCD at
`platform/1-foundation` and recurses for `*/application.yaml`, that each component Application is
Helm- or manifest-sourced with a pinned version, and that sync-wave annotations order the rollout,
cert-manager first and Backstage last. Read-only. No tool that mutates the cluster.

**What usually goes wrong:** the agent offers to apply immediately, or pads the explanation.

**What to do:** the prompt says "do not apply yet" and "a few sentences" for a reason. If the answer
runs long, that is a prompt to tighten rather than a problem with the platform.

### Apply the foundation App-of-Apps

**Prompt:**
> Apply the foundation App-of-Apps at `platform/0-bootstrap/root-app.yaml` into the `argocd`
> namespace. This is the bootstrap exception to the GitOps rule. Then watch the ArgoCD UI as
> the sync waves cascade and tell me when the foundation plane is all green.

**A good response** runs `kubectl apply -n argocd -f platform/0-bootstrap/root-app.yaml`, which
triggers an approval prompt because it is a mutating verb, then watches sync status. The waves
cascade: cert-manager, then secrets and policy, then observability, then the Argo extensions, then
Backstage.

**What usually goes wrong:** image pulls delay a wave. Backstage is last and slowest. A component
flaps Progressing before it settles Healthy.

**What to do:** give it time. The sync waves are ordered deliberately, and a component that is
Progressing is not a component that is broken. Open Backstage in a browser yourself once it is
Healthy; that is not something to ask the agent for.

---

## Chapter 6: the AI gateway

### Apply the AI plane and review the gateway

**Prompt:**
> Apply the AI plane App-of-Apps and, once it syncs, explain what the Gateway and its routes
> are doing: which backends exist, and what traffic each route carries.

**A good response** applies the plane, waits for the Gateway to report `Programmed=True`, and
explains that routes attach to `agentgateway-proxy` and carry traffic to the model and the MCP
server.

**What usually goes wrong:** the Gateway sits `Programmed=False`, or routes report
`Accepted=False` with "no parent found", which reads like a route defect and is not one.

**What to do:** check the Gateway first. Routes cannot attach to a Gateway that has not programmed,
and the listener admits routes by namespace label, so a route in an unlabelled namespace is refused
with a message about hostnames.

### Review the agentgateway data plane

**Prompt:**
> Show me how a request from an agent reaches the model: the Gateway, the route, the backend,
> and where the guardrail and audit policies attach.

**A good response** traces the path and names where the prompt-guard and audit policies sit. The
point is that the agent's traffic passes through the gateway rather than around it.

**What usually goes wrong:** the agent describes a direct call from the agent to the model, because
that is the more common pattern in its training data.

**What to do:** an agent that calls the model directly bypasses every control this plane installs,
and the platform would then certify guardrails nothing traverses. If the explanation skips the
gateway, ask where the guardrail policy applies and it will find the gap itself.

---

## Chapter 7: the agent runtime

### Write the kagent Agent CRD

This is the one worth taking slowly. It is the prompt most likely to be answered from stale
training data.

**Prompt:**
> Write a kagent Agent that acts as a platform helper: it answers questions about this
> platform's components and golden paths, keeps answers short and concrete, and says so when
> it does not know. Route it at the in-cluster vLLM through a ModelConfig, not any external
> provider. Put it in the `kagent` namespace, commit it under
> `platform/2-ai-plane/demo-agent/manifests/`, and let ArgoCD reconcile it.

**A good response** produces the Agent plus its ModelConfig and the dummy key Secret, in this exact
shape:

- `apiVersion: kagent.dev/v1alpha2`, `kind: Agent`, `spec.type: Declarative`
- `spec.declarative.systemMessage` (not `systemPrompt`), `spec.declarative.modelConfig: vllm-qwen3`
- ModelConfig `provider: OpenAI`, `model: qwen3-1.7b`, `openAI.baseUrl` pointed at the in-cluster
  gateway, key from a Secret, which vLLM ignores
- the `agentic-platform.io/llm-guard-policy` annotation, so it satisfies the Kyverno
  require-llm-guard-reference policy

It commits to Git and ArgoCD reconciles it. An agent, declared as a Kubernetes resource, deployed by
GitOps, written by an agent.

**What usually goes wrong:** all of it from stale training data. `v1alpha1` instead of `v1alpha2`.
`systemPrompt` instead of `systemMessage`. The field not nested under `spec.declarative`. A real
external provider instead of the vLLM ModelConfig. `baseUrl` pointed at the wrong Service.

**What to do:** the known-good artifact is at
`solution/platform/2-ai-plane/demo-agent/manifests/demo-agent.yaml`. Diff against it rather than
arguing with the agent. If it drifts on the CRD shape, tell it the apiVersion and field name
explicitly; the rest usually follows.

### Have the agent call an MCP server through the gateway

**Prompt:**
> Have the platform-helper agent call the MCP server through agentgateway, then show me the
> audit log entry for that call.

**A good response** triggers the agent-to-MCP call routed via agentgateway, and the audit entry
appears. The routing and the audit are the point, not the tool's output.

**What usually goes wrong:** the MCP server is deployed but its route is not attached, or the audit
entry lags behind the call.

**What to do:** if the call returns an error about extracting tools from the tool set, the gateway
is reporting honestly and its upstream is refusing connections. Check that the MCP server pod
actually started: it needs a numeric `runAsUser` on the pod and an explicit `cmd`, and it fails in a
way that looks like a gateway fault.

### Block a prompt injection

**Prompt:**
> Send the prompt-injection test fixture at the agent. Show me LLM Guard intercepting and
> blocking it, and the blocked request in the audit log.

**A good response** fires the repo's injection fixture, LLM Guard blocks it deterministically, and
the block appears in the audit log. The exact injection string is a committed fixture so the result
is reproducible rather than a lucky demonstration.

**What usually goes wrong:** config drift changes the verdict, or the block happens with no visible
audit line.

**What to do:** the verdict is deterministic against the pinned config. If it drifts, reset to the
committed fixture rather than tuning until it passes.

### Find the trace

**Prompt:**
> Open the trace from the agent's MCP call in Tempo. Walk the spans and point out the GenAI
> semantic-convention attributes: model, token counts, tool calls. Then load the AI-plane
> Grafana dashboard.

**A good response** opens the trace, walks the spans, and highlights the `gen_ai.*` attributes,
described as current but unstable, because the conventions are Development grade.

**What usually goes wrong:** there is no trace, because agent tracing is off by default in the
kagent chart. Or the agent searches for spans named `gen_ai.*` and finds none.

**What to do:** `otel.tracing.enabled` is the switch that works. The annotation that looks like it
should enable tracing does not, because the agent is a Go binary and no `Instrumentation` resource
exists. Spans are named for their operation and target, like `invoke_agent platform_helper` and
`execute_tool echo`, with `gen_ai.*` in the attributes. Nothing is named `gen_ai.*`.

---

## Chapter 8: model serving

### Serve an inference

**Prompt:**
> Send one inference request to the vLLM model through its OpenAI-compatible endpoint and show
> me the response.

**A good response** sends one request and shows the answer. Warm, expect a few seconds; cold, rather
longer while the model loads.

**What usually goes wrong:** the InferenceService sits `Ready=False` with "Predictor ingress not
created" while the predictor is running and serving perfectly well.

**What to do:** that message is about an Istio ingress this platform does not run.
`kserve.controller.gateway.disableIngressCreation` settles it. Check whether the predictor pod is
serving before believing the readiness condition.

---

## Chapter 9: the golden path

### Write the scaffolder template

**Prompt:**
> Write a Backstage scaffolder template for an `agent-service`. The form takes an agent name,
> purpose, model route, and the MCP tools it is allowed. On submit it generates a repo
> containing a kagent Agent CRD, an agentgateway route, an LLM Guard policy reference, and
> OTel instrumentation defaults. Commit it under `platform/3-self-service/agent-service/`.

**A good response** completes the template skeleton: parameters for name, purpose, model and tools,
`fetch:template` over the skeleton, and output including `catalog-info.yaml` and the agent
manifests.

**What usually goes wrong:** legacy scaffolder action names, choices hardcoded that the form should
take as parameters, or skeleton placeholders left literal.

**What to do:** the skeleton exists under `solution/platform/3-self-service/agent-service/`. The
Gitea host and org are templated values, not literals to fill in by hand.

### Write the ApplicationSet

**Prompt:**
> Write the ApplicationSet that watches the in-cluster Gitea for repos generated by this
> template and auto-creates an ArgoCD Application for each. Commit it at
> `platform/3-self-service/applicationset.yaml`.

**A good response** produces an SCM-provider ApplicationSet pointed at the in-cluster Gitea org,
templating one Application per generated repo.

**What usually goes wrong:** the generator points at the wrong Gitea URL, or the apply fails on
annotation size.

**What to do:** the ApplicationSet CRD exceeds the client-side apply annotation limit, so it needs
`kubectl apply --server-side --force-conflicts`.

### Fire the golden path

You act as the developer requesting a service here. The agent assists if needed.

**Prompt:**
> Through the Backstage portal, request a new agent: fill the form and submit. Then watch the
> chain: scaffolder generates the repo, the ApplicationSet creates the Application,
> ArgoCD syncs it, the agent runs, and the first trace lands in Tempo.

**A good response** is the whole chain completing, form to trace. This is the loop the platform
exists to close.

**What usually goes wrong:** any link stalls. Scaffold, ApplicationSet detection, sync, or trace.

**What to do:** work backwards from the last thing that did happen. Each link leaves a visible
artifact: a repo in Gitea, an Application in ArgoCD, a pod, a span.

---

## Chapter 10: governance and attribution

### Have Kyverno deny a violating agent

This is the second sanctioned use of mutating `kubectl`.

**Prompt:**
> Flip the AI-plane Kyverno policies from audit to enforce. Then try to apply the violating
> agent fixture (no LLM Guard reference) and show Kyverno denying it.

**A good response** turns on enforce mode, then applies the violating fixture. Two controls fire in
sequence: your agent stops and asks you to approve a mutating verb, and then Kyverno denies the
resource at admission. One control is at the agent, the other is in the cluster.

**What usually goes wrong:** the policy is still in audit, so the resource is admitted, or the
fixture used does not actually violate anything.

**What to do:** confirm enforce mode before concluding the policy does not work. Each policy ships a
violating fixture next to it. The denial is deterministic.

### Attribute every action to an agent

**Prompt:**
> Run the Loki query that shows every action in this cluster attributed to a named agent
> identity, including this Claude Code session's own actions from the audit hook.

**A good response** returns per-agent attributed actions, including your own agent's tool
invocations, shipped by the audit hook in `.claude/hooks/audit.sh`. The agent that built the
platform appears in the platform's own audit trail.

**What usually goes wrong:** the hook shipped nothing, so the Loki label is missing, or the query
filters on the wrong label.

**What to do:** the query and its label contract are in `prompts/queries/`. Check the hook is
actually running before debugging the query.
