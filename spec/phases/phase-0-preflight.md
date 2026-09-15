# Phase 0: Preflight (chapter 2)

**Goal:** Confirm the starting conditions before building anything. Install nothing in this phase.

**Inputs:** A bare Kubernetes cluster, up, with credentials provided. Your agentic CLI registered and able to run against the cluster.

**Outputs:**
- Confirmation that `kubectl` reaches the cluster and the nodes are Ready
- Confirmation of the Kubernetes version (expect 1.35)
- A read of this spec (`spec/BUILD-SPEC.md`) and `components.yaml`
- The repo cloned into your working environment so the spec and manifests are available
- A short written note of what is and is not present on the cluster (it should be close to empty)

**Test criteria (`tests/test_phase_0_preflight.py`):**
- `kubectl get nodes` returns at least one Ready node
- The server Kubernetes version is 1.35 (or the pinned version in `components.yaml`)
- The `argocd` namespace does not exist yet (this is a bare cluster)
- No ArgoCD Applications exist yet
- `components.yaml` parses and every entry is version-pinned

**Completion promise:** `<promise>PHASE0_DONE</promise>`

**Key decisions:**
- Do not install ArgoCD or any component in this phase. Phase 0 only confirms the ground truth.
- Cloning the repo is allowed and expected; it is how the spec and manifests reach your environment.
- If `kubectl` cannot reach the cluster, stop and resolve credentials before going further. Do not proceed on a cluster you cannot read.

**Stop here.** Output the completion promise and wait for the user. The frame for everything that follows: the cluster is bare, and from the next phase on your agent builds the platform.
