# Phase 1: GitOps bootstrap and core foundation (chapter 3)

**Goal:** ArgoCD installed and reconciling the App-of-Apps, with the core foundation (cert-manager, OpenBao, External Secrets Operator, Kyverno) synced and healthy.

**Inputs:** A bare cluster confirmed by Phase 0. The repo cloned. AWS Load Balancer Controller and the EBS CSI driver are provided by the cluster's add-ons (out of the in-cluster build scope).

**Outputs:**
- ArgoCD installed via server-side apply (the one allowed direct install), pinned to chart 9.5.22 (app v3.4.4)
- The root App-of-Apps applied, reconciling `platform/1-foundation/`
- cert-manager (v1.20.2), OpenBao (dev mode, app v2.5.5, chart 0.28.4), External Secrets Operator (v2.6.0, chart 2.6.0), Kyverno (chart 3.8.1, app v1.18.1) synced and healthy
- The ESO ClusterSecretStore (vault provider) wired to OpenBao, a seed Job, and a demo ExternalSecret (openbao-config)
- A gp3 StorageClass marked default (the cluster ships none)

**Test criteria (tests/test_phase_1_foundation.py):**
- ArgoCD server, repo-server, and application-controller are Ready
- The app-of-apps Application exists and is Synced
- cert-manager, external-secrets, openbao, kyverno Applications are Synced and Healthy
- The OpenBao ClusterSecretStore reports Ready and the demo ExternalSecret materializes a Secret
- A default StorageClass exists (gp3) and is the only default
- No Application is OutOfSync

**Completion promise:** `<promise>PHASE1_DONE</promise>`

**Key decisions:**
- Install ArgoCD CRDs with `kubectl apply --server-side --force-conflicts`; the ApplicationSet CRD exceeds the client-side apply annotation limit. This is the bootstrap exception to the GitOps rule.
- Author RBAC for the ArgoCD 3.x model: explicit `logs, get`; explicit `update/*` and `delete/*` on managed resources (3.0 stopped cascading).
- External Secrets Operator: use `external-secrets.io/v1` (v1beta1 is retired) and add Argo CD `ignoreDifferences` on `/spec/dataFrom`, `/spec/data`, `/spec/refreshInterval` to stop conversion-webhook drift.
- Kyverno chart is 3.8.1 (the 3.x line), app v1.18.1. Write new policies as CEL types; the AI-plane policies arrive in Phase 4.
- OpenBao runs in dev mode (one unsealed in-memory pod, fixed root token, KV v2 at `secret/`, injector off). ESO reads it over the Vault-compatible API via the vault provider in openbao-config. This is a workshop choice, not production: in production enable OpenBao Kubernetes auth and durable storage. Vault itself was not used because it relicensed to BUSL in 2023; OpenBao is the LF/MPL-2.0 fork.

**Stop here.** Output the completion promise and wait. This is the point to read the App-of-Apps reconcile and watch the sync waves land in order, before anything else is added on top.
