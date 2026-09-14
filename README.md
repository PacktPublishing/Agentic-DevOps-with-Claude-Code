<p align="center">
  <img src="docs/images/hero.png" alt="An orchestrating agent assembling a layered Kubernetes platform" width="100%">
</p>

# Agentic DevOps with Claude

**An AI-native Internal Developer Platform, built live by an agent, on Amazon EKS.**

[![License: MIT](https://img.shields.io/badge/License-MIT-FA7040.svg)](LICENSE)
[![Components](https://img.shields.io/badge/components-30%20pinned-2e9e5b.svg)](components.yaml)
[![GitOps](https://img.shields.io/badge/GitOps-ArgoCD-blue.svg)](solution/platform/0-bootstrap)
[![tests](https://github.com/PacktPublishing/Agentic-DevOps-with-Claude-Code/actions/workflows/tests.yml/badge.svg)](https://github.com/PacktPublishing/Agentic-DevOps-with-Claude-Code/actions/workflows/tests.yml)

A complete, reproducible platform you can build on your own cluster, one phase at a time, at
whatever pace suits you. Every component is here, version-pinned, with a test that proves each phase
landed.

It was first built live, by an agent, in front of an audience at a Packt workshop on 23 July 2026,
and then across 250 clusters. That is where the numbers below come from, and it is why the defects
are written down rather than quietly patched: they were found in front of people. Nothing here was
demoed from a slide.

> "Tools don't transform organizations. People do."

---

## What actually happened

The workshop was not a scripted demo. Attendees got a bare EKS cluster and an agent, and built the
platform themselves from the same spec in this repository. What that took to support:

| | |
|---|---|
| **250 single-tenant clusters** | provisioned and torn down cleanly across five AWS accounts, roughly 2h45m at 40-wide |
| **Every ArgoCD Application** | Synced and Healthy from a cold provision, zero manual steps. See the caveat below; that is not the same as every component working |
| **~7 minutes** | bare cluster to a converged foundation plane |
| **30 components** | every one version-pinned in [`components.yaml`](components.yaml) and frozen before the event |
| **Real inference** | vLLM serving an in-cluster model, no external API spend, no credentials to leak |

The defects found during the live run were not quietly patched out. They were remediated in the
manifests, and the reasoning sits in a comment at the point of the fix rather than in a changelog
nobody opens.

**The caveat on that green dashboard is worth stating plainly, because it is the most useful thing
in this repository.** ArgoCD reports an Application Healthy when it cannot assess what is inside it.
Running this platform from cold in September 2026 produced a full board of green Applications while
the MCP server's init container had failed over a thousand times and the demo agent could load no
tools at all. Nothing was lying; ArgoCD simply had no health check for an `MCPServer`. A dashboard
that cannot go red is not a dashboard, so this repo now ships health checks for the custom resources
its readiness depends on, and a test that fails if a new kind arrives unassessed.

## What the platform contains

Three planes, built in order, each reconciled by ArgoCD from Git.

**Cloud-native foundation.** Backstage as the developer portal, the full Argo stack (CD, Workflows,
Events, Rollouts), an OpenTelemetry observability plane with Prometheus, Loki and Tempo,
cert-manager, Kyverno for policy, and External Secrets backed by OpenBao.

**AI plane.** kgateway and agentgateway for agent traffic, kagent for declarative agents as
first-class Kubernetes objects, LLM Guard for prompt-injection defense, OpenLLMetry emitting OTel
GenAI semantic conventions, and KServe serving a CPU model through vLLM, with llm-d for the
distributed-inference picture.

**Self-service golden path.** A Backstage scaffolder template that generates a governed agent, wired
through an ArgoCD ApplicationSet so the platform deploys it without a human in the loop.

## The engineering worth reading

If you are skimming this as a portfolio piece, these are the parts with real decisions in them.

- **[`docs/architecture.md`](docs/architecture.md)** carries the settled decisions and why. EKS Pod
  Identity over IRSA. Audit-mode policy before enforcement. Why MetalLB and ingress-nginx are the
  wrong answer on EKS in 2026. [`docs/reference/decisions.md`](docs/reference/decisions.md) is the
  dated log of how each one was reached.
- **[`tests/test_platform_contract.py`](tests/test_platform_contract.py)** encodes the defect classes
  that recur in these manifests as assertions, so the same mistake cannot ship twice. Unsubstituted
  placeholders, `runAsNonRoot` without a numeric uid, registry hosts doubled into image paths.
- **[`solution/platform/2-ai-plane/agentgateway-runtime/`](solution/platform/2-ai-plane/agentgateway-runtime)**
  is the densest part. Its README explains why the Gateway cannot be named after the chart that
  installs its controller, which is the kind of failure that reports a successful sync and a dead
  data path at the same time.
- **The comments are the documentation.** Where a manifest carries a value that looks arbitrary, the
  comment above it says which symptom appeared without it. Most of them cost somebody a cluster
  build to find.
- **[`docs/what-is-not-included.md`](docs/what-is-not-included.md)** lists what was stripped before
  publication and why, including a security finding that is described rather than shipped: the
  browser terminals used at the live event had no authentication.

## Repo map

- [`spec/`](spec) the spec the agent builds from, plus a file per phase describing what that phase
  must be true of when it finishes.
- [`components.yaml`](components.yaml) the pinned component set and single source of truth.
  [`versions.lock.md`](versions.lock.md) is the quick lookup, generated from it by
  [`scripts/gen-versions-lock.py`](scripts/gen-versions-lock.py) and tested for drift.
- [`solution/platform/`](solution/platform) the reference build, numbered in build order:
  `0-bootstrap` (ArgoCD and the App-of-Apps), `1-foundation`, `2-ai-plane`, `3-self-service`.
- [`charts-vendor/`](charts-vendor) vendored Helm charts, so nothing waits on the network mid-build.
  Every tarball is asserted to match its pin.
- [`prompts/prompt-library.md`](prompts/prompt-library.md) the prompts that drive each phase.
- [`scripts/`](scripts) image mirroring, chart vendoring, reset to a checkpoint, preflight, smoke
  test, and the probes the phase tests use.
- [`docs/`](docs) the architecture record, the decision log, version maintenance, and
  [what was left out](docs/what-is-not-included.md).
- [`tests/`](tests) the contract tests and one pytest file per build phase.
- [`docs/reference/`](docs/reference) the primary-source trail: the build spec, the version research
  with its sources, and the locked architectural decisions including the ones later reversed.
- [`images/`](images) the container images with no upstream. The web terminal in there is workshop
  distribution machinery with a known security finding, and its README says so before you read the
  Dockerfile.

## Running it yourself

You need an EKS cluster, an agentic CLI on your own plan, and the prerequisites in
[`docs/prerequisites.md`](docs/prerequisites.md). Point your agent at
[`spec/BUILD-SPEC.md`](spec/BUILD-SPEC.md) and let it build, one phase at a time.

Each phase has a test that tells you whether it actually landed, in [`tests/`](tests), named for the
phase it gates. Run `pytest` for the checks that need no cluster; set `KUBECONFIG_FILE` and
`EXPECTED_CONTEXT` for the ones that do. Those two variables are deliberate: nothing here reads your
default kubeconfig, so a test cannot touch a cluster you did not name.

If a phase breaks, or you would rather skip ahead, the reference build in `solution/platform/` is
the answer key: copy the component you are stuck on out of it, commit, and let ArgoCD reconcile.
Each plane has its own App-of-Apps in [`solution/platform/0-bootstrap/`](solution/platform/0-bootstrap),
applied in order, so you can jump in at the foundation, the AI plane or the self-service layer.

### Which ref to use

| | |
|---|---|
| **Tag [`v1.0.0`](../../releases/tag/v1.0.0)** | Reproduces the build exactly as delivered on 23 July 2026. Frozen; never re-pinned. |
| **`main`** | Maintained. Versions move on the cadence in [`docs/version-maintenance.md`](docs/version-maintenance.md), so it installs against a current cluster. |

The pins in `versions.lock.md` were frozen for a four-hour live event, which is the right policy for
a live event and the wrong one for a repo people run for years. So the freeze belongs to the tag and
`main` is maintained.

**Kubernetes 1.34 or newer.** The Phase 0 gate asserts a floor rather than an allow-list of exact
minors, so a newer cluster is fine; that gate broke every reader on the day 1.37 shipped, and
[`tests/test_version_gate.py`](tests/test_version_gate.py) now fails the build if anyone reverts it.

## Honest framing

Components carry real maturity labels. Sandbox projects are described as Sandbox. The OTel GenAI
semantic conventions are current but unstable, and the repo says so rather than implying they are
settled. Versions were pinned and frozen before the event, nothing was built from source live, and
every image was served from a mirror so the build stayed fast and self-contained.

Where something is broken or unfinished, it is labelled at the point it matters rather than
collected in a status page. Tempo keeps no volume and says so in its own manifest; the prompt-guard
annotation the policy requires does not produce the traces and says so where it is set.

## License

MIT. See [`LICENSE`](LICENSE).
