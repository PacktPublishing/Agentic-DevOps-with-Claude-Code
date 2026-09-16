# Bootstrap

How the cluster goes from empty to `checkpoint/module-0-start` (ArgoCD installed, nothing else synced), then to the foundation plane.

## 1. Install ArgoCD (the one allowed direct install)

ArgoCD is installed via its Helm chart, pinned to the version in `versions.lock.md`. This is the bootstrap exception to the GitOps rule: everything after this flows through ArgoCD.

```bash
helm install argo-cd argo-cd \
  --repo https://argoproj.github.io/argo-helm \
  --version 9.5.22 \
  --namespace argocd --create-namespace \
  --values argocd-values.yaml \
  --set crds.install=true
```

`argocd-values.yaml` (in this directory) adds a health check for the KServe
InferenceService so a serving model reads Healthy rather than Progressing (see the file for
why). Run this from the bootstrap directory, or point `--values` at the file's full path.

The chart and ArgoCD CRDs install cleanly client-side at this size. For the ApplicationSet and Argo Workflows CRDs later, use server-side apply.

## 2. Apply the plane App-of-Apps (one per module)

The platform is a plane-of-apps: one App-of-Apps per plane, applied at the start of its
module, so each module shows GitOps doing the work.

- `root-app.yaml` (`platform-foundation`): the foundation plane, applied in Module 1.
- `ai-plane-app.yaml` (`platform-ai-plane`): the AI plane, applied in Module 2.
- `self-service-app.yaml` (`platform-self-service`): the self-service ApplicationSet, applied in Module 3.

Each points ArgoCD at its plane directory and recurses for the per-component Application
manifests. They read from a Git host running inside the cluster, so that host has to exist and
hold your tree before any of them will sync.

## The supported path

`./provision/seed-gitea.sh` does the whole bootstrap. It installs Gitea, creates the
`platform/packt-agentic-devops` repository, pushes your working tree into it, and applies
`root-app.yaml`.

It works because of one asymmetry: Gitea's own Application pulls its chart from
`dl.gitea.com`, not from Gitea, so it is the one Application that can be applied before a Git
host exists. Everything else follows from it.

Afterwards, `./provision/push-to-cluster.sh` sends each new commit to the in-cluster host. That
is the loop the platform is built around: commit locally, push to the cluster, watch ArgoCD
reconcile. Your local clone stays the source of truth, because the in-cluster copy dies with
the cluster.

## The direct-apply path, for debugging only

The per-component Applications under `platform/1-foundation/<name>/application.yaml` that are
Helm-sourced pull their charts straight from upstream, so they can be applied without any Git
host at all:

```bash
kubectl apply -n argocd --recursive -f platform/1-foundation/
```

**This is a debugging aid, not a way to build the platform.** Twenty-two Applications in this
repository carry raw manifests rather than upstream charts, and every one of them is sourced
from the in-cluster Git host. Skipping the seed skips all of them: `cert-manager-issuers`,
`gitea-config`, `openbao-config`, `policy-baseline`, and the entire AI plane. Use it to
inspect one component in isolation, not to get to a working platform.

## Sync waves

- Wave 0: cert-manager (issues webhook certs others depend on).
- Wave 1: secrets and policy tooling (external-secrets, openbao, kyverno).
- Wave 2: scaling and delivery extensions (keda, argo-rollouts), then observability.
- Later waves: Backstage last.

## Checkpoint

After ArgoCD is installed and before any foundation sync, tag `checkpoint/module-0-start`.
