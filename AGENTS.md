# AGENTS.md

Project memory for this repository, written for two readers: someone working through the book, and
the coding agent they point at this tree.

An agent builds an AI-native Internal Developer Platform on Amazon EKS from the spec in `spec/`, one
phase at a time, and `tests/` proves each phase landed. `solution/` is the finished build, for when
you want to compare rather than debug.

Start with `docs/prerequisites.md`, then `provision/README.md` for the cluster, then
`spec/BUILD-SPEC.md`. Chapter N of the book is phase N minus 2: chapter 3 is
`spec/phases/phase-1-foundation.md`, chapter 10 is `spec/phases/phase-8-governance.md`.

`docs/architecture.md` holds the settled decisions, `docs/reference/decisions.md` the dated log of
how they were reached, and `docs/what-is-not-included.md` explains what was left out, so a reference
that looks broken has an answer.

## Manifest defect classes that recur here. Check for each before believing a build is healthy.

Every one of these produces a component that reports Synced, reports Healthy, and does not work.

1. **An unsubstituted `REPLACE_WITH_*` placeholder.** `grep -rn REPLACE_WITH platform/` must return
   nothing once `provision/cluster-facts.sh` has run. The reference under `solution/` keeps its
   placeholders on purpose. Anything unsubstituted in your working copy leaves an Application
   Degraded forever.
2. **`runAsNonRoot: true` with no numeric `runAsUser`** on an image whose USER is root or
   non-numeric, which the kubelet refuses with `CreateContainerConfigError` before the container
   starts. Pin the uid the image actually uses; verify with `id` inside it rather than guessing. Hit
   on vLLM, llm-guard, the openbao and gitea seed jobs, and the MCP server. On a pod with an
   injected init container the uid has to go on the **pod**, because the init container writes into
   an emptyDir that needs `fsGroup`.
3. **An image `repository` that repeats the registry host** (`registry: ghcr.io` plus
   `repository: ghcr.io/...`), producing a doubled path. Repository must not include the host.
4. **A directory the container cannot traverse.** `Cannot find module '/app/...'` for a path that
   demonstrably holds the module is a permission problem, not a missing build.
5. **Hardcoded credentials that drift.** Read shared credentials from one Secret, never a second
   copy in a Job manifest.
6. **A custom resource ArgoCD cannot assess.** ArgoCD reports Healthy for anything it has no health
   check for, so a broken `MCPServer` or `Agent` shows green. `solution/platform/0-bootstrap/argocd-values.yaml`
   carries the checks and `tests/test_argocd_health_checks.py` fails if a new kind arrives unassessed.

`tests/test_platform_contract.py` asserts 1 through 5. Run the cluster-free suite after any manifest
change:

```bash
uv run --with pytest --with pyyaml --with jsonschema python -m pytest -q
```

## What this repo is

A GitOps-driven, AI-native Internal Developer Platform. ArgoCD reconciles everything from Git. The
foundation plane is cloud-native (Backstage, the Argo stack, the observability plane, policy and
secrets tooling). The AI plane adds agent infrastructure (kgateway, agentgateway, kagent, LLM Guard,
OpenLLMetry, KServe with vLLM, llm-d).

## Repo map

- `provision/` holds the Terraform that creates the cluster, plus the bootstrap and teardown
  scripts. Start at `provision/README.md`; it opens with what the cluster costs to run.
- `components.yaml` is the single source of truth for the component set. Every entry carries a
  pinned version. CI fails if any entry is unpinned.
- `versions.lock.md` records the pinned chart and image versions with the resolution date. It is
  generated from `components.yaml` by `scripts/gen-versions-lock.py`.
- `solution/platform/0-bootstrap/` holds the ArgoCD install, its values, and one App-of-Apps per plane.
- `solution/platform/1-foundation/` holds one directory per foundation component.
- `solution/platform/2-ai-plane/` holds one directory per AI-plane component.
- `solution/platform/3-self-service/` holds Backstage templates and the ApplicationSet.
- `platform/` is **your** working copy, the tree your agent builds and the one ArgoCD reads once you
  push it to the in-cluster Git host. It does not exist until you create it.
- `charts-vendor/` holds vendored Helm charts, so nothing waits on the network mid-build. Every
  tarball is asserted to match its pin.
- `scripts/` holds chart vendoring, image mirroring, smoke tests, and the probes the phase tests use.
- `prompts/` holds the prompts that drive each phase.
- `spec/` holds the build spec and one file per phase.

## Getting to a running platform

```bash
terraform -chdir=provision apply          # the cluster
$(terraform -chdir=provision output -raw update_kubeconfig)
cp -a solution/platform/. platform/       # or let the agent generate platform/
./provision/cluster-facts.sh              # fills in cluster name, VPC id, region
helm install argo-cd ...                  # see solution/platform/0-bootstrap/README.md
./provision/seed-gitea.sh                 # installs the Git host, seeds it, starts ArgoCD
```

Afterwards, `./provision/push-to-cluster.sh` sends each commit to the cluster. Tear down with
`./provision/destroy.sh`, which releases the load balancers and volumes before destroying, because
`terraform destroy` alone leaks them.

## GitOps rules

- Cluster context safety: every kubectl and helm command sets an explicit `KUBECONFIG` and never
  writes to `~/.kube/config` on a machine that has other clusters in it. Verify
  `kubectl config current-context` matches the cluster you created before any mutating command.
  Only touch clusters you created.
- All cluster changes flow through Git. ArgoCD applies them.
- Install first, enforce last. Every Kyverno policy (foundation `policy-baseline` and AI-plane
  `ai-policies`) ships with `failureAction: Audit`, not `Enforce`. Audit reports violations without
  blocking admission. An admission guardrail set to Enforce before the software meant to satisfy it
  is installed rejects that software's own pods and stalls the build. So the whole platform lands
  under Audit, then enforcement is turned on only after the platform is healthy. The single
  sanctioned flip to Enforce is the governance demonstration on the AI-plane set; the foundation
  baseline stays Audit. Do not add a namespace-wide enforcing admission webhook that fires before
  its backing workload exists.
- Never run mutating `kubectl` directly against the cluster, except for the bootstrap (installing
  ArgoCD and seeding the Git host) and the scripted Kyverno denial demonstration.
- Bootstrap and ApplicationSet CRDs require server-side apply: use
  `kubectl apply --server-side --force-conflicts`. The ApplicationSet and Argo Workflows CRDs exceed
  the client-side apply annotation limit.
- ArgoCD is on the 3.x line. Server-side apply and server-side diff are the modern default. RBAC
  changed in 3.0: `update` and `delete` no longer cascade to managed sub-resources, and logs need
  explicit `logs, get` permission.

## Naming and namespaces

- Descriptive kebab-case everywhere. No UUIDs, no `final-v2` suffixes. No `improved`, `new`, or
  `enhanced` in names.
- One namespace per logical area: `argocd`, `backstage`, `observability`, `cert-manager`, `kyverno`,
  `external-secrets`, `openbao`, `kgateway-system`, `agentgateway`, `kagent`, `kserve`.

## Platform facts that are easy to get wrong (verified June 2026)

- ingress-nginx is end of life and MetalLB is decorative on EKS. The ingress and LB path is the AWS
  Load Balancer Controller. Storage is the AWS EBS CSI driver.
- Workload identity is EKS Pod Identity, not IRSA. Both the AWS Load Balancer Controller and the EBS
  CSI driver use it; the cluster sets `enable_irsa = false` so no OIDC provider is created. The EBS
  CSI association is wired through the add-on's `pod_identity_association` so EKS owns the ordering;
  the LB controller uses a standalone association. This is a locked decision (D16). Read
  `docs/architecture.md` and `docs/reference/decisions.md` before changing it, and record a
  superseding entry; do not silently revert to IRSA.
- The kagent Agent CRD is `kagent.dev/v1alpha2`. The field is `systemMessage`, nested under
  `spec.type` and `spec.declarative`. Agents run on Google ADK. Do not write v1alpha1 or
  `systemPrompt`.
- agentgateway is a Linux Foundation (Agentic AI Foundation) project, not CNCF. It is a sibling of
  kgateway, not its data plane.
- The demo agent routes to the in-cluster vLLM **through agentgateway**, not directly, so the
  prompt-guard and audit policies apply to it. An agent that calls the model directly bypasses every
  control the AI plane installs, and the platform then certifies guardrails nothing traverses. No
  external API spend, no external credentials.
- The Gateway must not be named after the chart that installs its controller. The controller creates
  one Deployment per Gateway named after the Gateway; the agentgateway chart's own Deployment carries
  the release name; `spec.selector` is immutable, so naming both `agentgateway` fails permanently
  while ArgoCD reports the sync succeeded. It is `agentgateway-proxy`.
- Agent tracing is **off** by default in the kagent chart. `otel.tracing.enabled` is the switch that
  works. The `instrumentation.opentelemetry.io/inject-python` annotation does not: the agent is a Go
  binary, kagent does not copy Agent annotations onto the Deployment it generates, and no
  `Instrumentation` resource exists. The annotation stays because a policy requires it; it is not
  what produces the traces.
- OTel GenAI spans are named for their **operation and target** (`invoke_agent platform_helper`,
  `execute_tool echo`, `generate_content qwen3-1.7b`), with `gen_ai.*` in the **attributes**. Do not
  match spans by a `gen_ai.*` name; nothing is named that way.
- OpenTelemetry GenAI semantic conventions are Development grade. Present `gen_ai.*` attributes as
  current but unstable.

## Testing

Cluster-free tests run anywhere. Cluster-bound tests skip themselves unless `KUBECONFIG_FILE` and
`EXPECTED_CONTEXT` are set, so a bare `pytest` is safe with no cluster and reports them as skipped.
Nothing reads the default kubeconfig, on purpose.

```bash
uv run --group test pytest          # everything the suite needs
pytest                              # whatever your environment already has
```

## Container images

Six manifests pull from `ghcr.io/peopleforrester/*`. They pull anonymously and you do not have to
do anything about them.

Four are mirrors of upstream images, re-hosted so a build cannot be stopped by a Docker Hub rate
limit. Two have no upstream and are built here: `images/backstage/` scaffolds a Backstage app and
builds it, and `images/vllm-qwen3/` bakes the Qwen3-1.7B weights into the upstream vLLM CPU image so
pods load from disk instead of downloading at startup.

To host all six yourself, run `scripts/mirror-images.sh` for the mirrors and the two
`build-and-push.sh` scripts for the built ones, all with the same `GHCR_ORG`. One manual step
follows: the MCP server manifest pins its image by digest, and a copy into another namespace gets a
new digest, which the mirror script prints.

## Writing standards for any doc generated here

- No em-dashes, no en-dashes. Commas, colons, periods.
- Banned words: delve, leverage, robust, seamless, comprehensive, under the hood, navigate
  complexities, genuinely, in today's landscape.
- No "it's not X, it's Y" inversions. No triadic lists as a default. No mirrored closing sentences.
- Direct and declarative. State things plainly. No hedging filler.
- Claims about maturity stay evidence-grounded. Sandbox projects are described as Sandbox. If
  evidence for a number does not exist, say so.

## Secrets

The repo contains zero real credentials, and no AWS account id. Both are verifiable rather than
asserted; `docs/what-is-not-included.md` gives the two commands and `tests/test_no_account_ids.py`
runs them. OpenBao (the LF/MPL-2.0 Vault fork, dev mode) is the in-cluster secret backend and
External Secrets Operator pulls from it over the Vault-compatible API. Sealed Secrets was dropped
(redundant with ESO, and Bitnami retired its chart repo). The two passwords that do appear, for the
in-cluster Gitea and OpenBao dev instances, are ephemeral and local to your own cluster.

## What must never be added here

This is a public companion repository for a book. Keep out of it:

- Anything that identifies a person, employer, client, or third-party event.
- Cloud resource identifiers: account ids, volume and instance ids, ARNs, load balancer hostnames.
- Links to private shares, and personal domains.
- Internal identifier schemes that have no key in this repository.
- Delivery material: run-of-show notes, recording checklists, anything addressed to a presenter
  rather than a reader.

`tests/test_no_account_ids.py` enforces the credential and account-id part of this, and CI runs it
on every push.
