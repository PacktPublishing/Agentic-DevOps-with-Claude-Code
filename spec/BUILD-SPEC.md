# Platform Build Spec

This is the spec your agentic CLI ingests. It drives the build of an AI-native Internal Developer Platform on your cluster, phase by phase, and each phase has a test in `tests/` that proves it landed.

For the reasoning behind a choice rather than the instruction, read [`docs/architecture.md`](../docs/architecture.md) and [`docs/reference/decisions.md`](../docs/reference/decisions.md). This file is the one you and your agent actually run.

## What you are building

An AI-native IDP on Amazon EKS: a cloud-native foundation (Backstage, the Argo stack, the OpenTelemetry observability plane, policy and secrets tooling) plus an AI plane that makes it AI-native (kgateway, agentgateway, kagent, LLM Guard, OpenLLMetry, KServe with vLLM, llm-d).

## Starting state

A bare Kubernetes cluster, up, with credentials. Nothing is installed. ArgoCD is not present and this repo is not yet cloned on the cluster side. Your agent does all of it.

## Non-negotiable rules

These bind your agent for the whole build.

1. **Work one phase at a time, and stop at the end of each phase.** Do not start the next phase until the user confirms. The stop is the point of the exercise: it is where you look at what was just built rather than watching it scroll past.
2. **Test first.** For each phase, write the phase test, run it to confirm it fails, build the components, then run it to confirm it passes. No mocks, no stubs, no fallbacks.
3. **Everything after the bootstrap flows through Git and ArgoCD.** The only direct installs are ArgoCD itself (the bootstrap) and the one scripted policy-denial demo. Use server-side apply for CRDs (`kubectl apply --server-side --force-conflicts`); the ApplicationSet and Argo Workflows CRDs exceed the client-side apply annotation limit.
4. **Pin every version.** Use the versions in `components.yaml` and `versions.lock.md`. Do not invent versions or use what your training data remembers.
5. **Two model roles, do not confuse them.** Your agentic CLI is the builder doing platform engineering. The model the deployed platform agents call is the small in-cluster vLLM served in Phase 6, over an OpenAI-compatible endpoint. There is no external LLM in the platform and no external API spend.
6. **No secrets in Git.** OpenBao (dev mode) and External Secrets Operator handle the in-cluster story.

## Sourcing

You are given the sources so you do not hunt for them or guess.

- **Charts** come from the pinned Helm repositories in `components.yaml`, vendored under
  `charts-vendor/` so nothing waits on the network.
- **Images**: pull from in-region ECR (the AWS-managed EKS add-on registry), `public.ecr.aws`, or
  the workshop GHCR namespace. **Never reference `docker.io` in a manifest.** Docker Hub
  rate-limits anonymous pulls and stalls the build. If a chart defaults to Docker Hub, override the
  image to the mirrored copy.
- **The App-of-Apps is a pattern, not a file to copy.** Generate a root `Application` per plane
  that points ArgoCD at that plane's directory and recurses for the per-component manifests, ordered
  by sync waves: cert-manager first, Backstage last.

## Build rules: avoid these known failures

Each rule prevents a specific failure that will otherwise leave an Application `Degraded` with a
confusing error. Follow them when you generate manifests.

1. **Per-cluster values are parameters, never hardcodes.** Anything that differs per cluster (the
   cluster name, the VPC id) is templated and substituted at provisioning. The AWS Load Balancer
   Controller needs both `clusterName` and `vpcId` set explicitly; do not leave `vpcId` to instance
   metadata, because under VPC-CNI prefix delegation that IMDS fetch times out and the controller
   crash-loops.
2. **`runAsNonRoot: true` always pairs with a numeric `runAsUser`.** On an image whose user is
   non-numeric, kubelet cannot verify non-root and the pod fails `CreateContainerConfigError`. Pin
   the image's actual numeric uid (find it: run `id` in the image). This bites seed Jobs especially.
3. **An image `repository` must not repeat the registry host.** Charts build the ref as
   `registry/repository`; `registry: ghcr.io` with `repository: ghcr.io/org/name` yields
   `ghcr.io/ghcr.io/org/name`, a wrong path. Use `repository: org/name`.
4. **The container's runtime user must be able to traverse its working directory.** `Cannot find
   module '/app/...'` for a path that clearly contains the module is a permission problem, not a
   missing file. A `WORKDIR` of `0700 root` under a non-root user cannot be entered.
5. **Read shared credentials from one source.** Never hardcode a password that also lives in a
   chart's values; they drift and every authenticated call then 401s. Reference the one Secret the
   platform creates.
6. **Install first, enforce last.** Every Kyverno policy ships with `failureAction: Audit`. An
   admission guardrail set to Enforce before the software it governs is installed rejects that
   software's own pods and stalls the build. The one sanctioned flip to Enforce is the governance
   demo (Phase 8) on the AI-plane set, after the platform is healthy.
7. **Validate before you apply.** A manifest that does not parse wastes a sync cycle. Round-trip
   the YAML (or `kubectl apply --dry-run=client`), and `helm template`/`helm lint` the chart with
   your values before committing.

When something does not converge, diagnose from ArgoCD status and the pod events, fix the root
cause **in the values file**, and commit. Deleting a pod does not fix a Git-sourced fault; ArgoCD
recreates it from Git. Fix Git.

## Completion gate per phase

A phase is done when its test passes and you have committed the phase's files. Output the phase completion promise, then stop and wait for the user.

## Phases

Nine phases, 0 through 8. Each maps to a chapter of the book: chapter = phase + 2.

| Phase | Name | Chapter | What it delivers |
|---|---|---|---|
| 0 | Preflight | 2 | Confirm the bare cluster, credentials, agent registration, and tooling. Read this spec and `components.yaml`. Install nothing. |
| 1 | GitOps bootstrap and core foundation | 3 | Install ArgoCD (server-side), clone and point at the repo, then the App-of-Apps brings up cert-manager, OpenBao, External Secrets Operator, and Kyverno. |
| 2 | Observability plane | 4 | kube-prometheus-stack, Loki, Tempo, the OpenTelemetry Collector and Operator. |
| 3 | Developer portal | 5 | Backstage (catalog, TechDocs, scaffolder, ArgoCD plugin), KEDA, and the Argo extensions (Workflows, Events, Rollouts). That completes the foundation: a working IDP. |
| 4 | AI gateway plane | 6 | Gateway API CRDs, kgateway, agentgateway with client-certificate mTLS, the prompt guardrail, and audit access logging. The AI-plane Kyverno policies are defined here in audit mode, so the AI plane is governed from birth. |
| 5 | Agent runtime and safety | 7 | kagent and an Agent CRD, LLM Guard, OpenLLMetry wiring. The agent calls an MCP server through agentgateway; a prompt-injection attempt is blocked. |
| 6 | Model serving | 8 | KServe with a small in-cluster vLLM model, and llm-d shown as the scheduling layer. The agent trace lands in Tempo. That completes the AI plane. |
| 7 | Self-service | 9 | A Backstage scaffolder template for an agent-service and the ArgoCD ApplicationSet that watches for it. The golden path fires end to end. |
| 8 | Governance and attribution | 10 | Flip the AI-plane Kyverno policies from audit to enforce, with the live denial demo. Per-agent attribution in Loki. |

Each phase has a detailed file in `spec/phases/phase-N-*.md` with its goal, outputs, test criteria, completion promise, and pinned versions.

## How to run this

1. Read this file and `components.yaml`.
2. Start at Phase 0. Read `spec/phases/phase-0-preflight.md`.
3. For each phase: read the phase file, write the test, confirm it fails, build, confirm it passes, commit, output the completion promise, then stop and wait for the user.
4. Move to the next phase only when the user says go.

## Status

The nine-phase breakdown is approved (decisions D8). Phases 0 through 8 are written in `spec/phases/`, each with goal, outputs, test criteria, completion promise, pinned versions, and a forced stop. Versions match `components.yaml` and `versions.lock.md` as of the June 19, 2026 spike sweep. Re-pin at the July freeze.
