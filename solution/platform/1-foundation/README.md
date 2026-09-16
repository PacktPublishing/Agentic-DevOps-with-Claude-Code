# 1-foundation: the cloud-native foundation plane

Built in Module 1. One directory per component, each with an ArgoCD `application.yaml` (Helm- or manifest-sourced, pinned) and any raw manifests under `manifests/`.

What lands here: Backstage, the Argo stack (Workflows, Events, Rollouts), the observability plane (OpenTelemetry, Prometheus, Grafana, Loki, Tempo), cert-manager, Kyverno, External Secrets with OpenBao, KEDA, the AWS Load Balancer Controller, and the AWS EBS CSI driver.

Applied via the foundation App-of-Apps at `../0-bootstrap/root-app.yaml`. ArgoCD sync-wave annotations order the rollout: cert-manager first, Backstage last.
