# Phase 3: Developer portal (chapter 5)

**Goal:** Backstage up with a populated catalog, plus the scaling and delivery extensions.

**Inputs:** Phases 1 and 2 complete. A pre-built Backstage image (Backstage is never built from source live).

**Outputs:**
- Backstage (chart 2.8.2, app on the 1.51 line) deployed from the pre-built image, catalog populated, TechDocs rendering, the ArgoCD plugin showing live sync state
- KEDA (chart 2.20.1) for event-driven pod autoscaling
- Argo Workflows (chart 1.0.16, app v4.0.6), Argo Events (chart 2.4.22, app v1.9.10), Argo Rollouts (chart 2.41.0, app v1.9.0)
- Backstage backed by PostgreSQL

**Test criteria (tests/test_phase_3_portal.py):**
- The backstage, keda, argo-workflows, argo-events, argo-rollouts Applications are Synced and Healthy
- Backstage answers on its service and the catalog returns at least one entity
- The ArgoCD plugin in Backstage returns live Application status
- KEDA, Argo Workflows, Argo Events, and Argo Rollouts CRDs are established

**Completion promise:** `<promise>PHASE3_DONE</promise>`

**Key decisions:**
- Backstage uses the New Frontend System (default since v1.49.0) and the new backend system; deploy a custom pre-built image, not the chart's demo image.
- Scaffolder templates are `scaffolder.backstage.io/v1beta3` with Nunjucks; the GitHub auth backend module is `@backstage/plugin-auth-backend-module-github-provider`. Guest auth is the default here, with the GitHub OAuth wiring present but commented out. Switch it on if you have an OAuth app; the catalog and scaffolder work either way.
- Argo Workflows full CRDs install server-side (they exceed the client-side annotation limit). Argo Events needs an explicit JetStream EventBus, not the deprecated STAN.
- KEDA is pod autoscaling, distinct from node provisioning.

**Stop here.** Output the completion promise and wait. Open the portal and confirm all three: the catalog has entities, the scaffolder lists a template, and the ArgoCD tab shows live Application state.
