# Phase 2: Observability plane (chapter 4)

**Goal:** The observability stack synced and collecting: metrics, logs, traces, and the OpenTelemetry pipeline.

**Inputs:** Phase 1 complete (ArgoCD, cert-manager, gp3 StorageClass). cert-manager is required before the OpenTelemetry Operator webhooks.

**Outputs:**
- kube-prometheus-stack (chart 86.3.2, operator v0.91.0; Prometheus v3.12.0, Grafana app v13.0.2, Alertmanager v0.33.0) synced, with Prometheus and Alertmanager on gp3 PVCs
- Loki (chart 17.4.7, app 3.7.2) in monolithic mode, from the grafana-community repo
- Tempo (single-binary chart 2.2.3, app 2.10.7) on port 3200
- OpenTelemetry Collector (chart 0.158.2) as a daemonset plus a deployment gateway, and the OpenTelemetry Operator (chart 0.115.0)

**Test criteria (tests/test_phase_2_observability.py):**
- The observability Applications are Synced and Healthy
- Prometheus and Alertmanager PVCs are Bound
- Grafana is reachable and has Loki and Tempo datasources (Tempo on 3200)
- The OpenTelemetry Collector daemonset has a pod Ready on each node
- A test trace sent via OTLP appears in Tempo

**Completion promise:** `<promise>PHASE2_DONE</promise>`

**Key decisions:**
- Use the grafana-community Helm repo for Loki and Tempo; the old grafana repo charts are frozen for Enterprise.
- Apply kube-prometheus-stack operator CRDs server-side before the release; Helm does not upgrade these CRDs and they exceed the client-side annotation limit.
- Disable the kubeScheduler, kubeControllerManager, and kubeEtcd scrape targets; the EKS control plane is managed and not scrapable.
- The OpenTelemetry Collector chart has no default mode or image repository; set both explicitly. OpenTelemetry is CNCF Graduated (May 2026).
- Loki monolithic for the demo; Simple Scalable is deprecated. Object storage (S3), not the bundled MinIO.

**Stop here.** Output the completion promise and wait. Find the trace in Tempo before moving on; a signal you have not seen arrive is a signal you cannot trust later.
