# Backstage image

This platform's Backstage image is built ahead of time and pushed to GHCR, then the
`backstage` Helm release runs it. Backstage is a framework: you scaffold an app, add
plugins, and build. This directory holds the overlay and the build automation, not the
generated app, which `create-app` produces and which is gitignored because it carries
its own dependency tree of roughly 1.9 GB.

You do not need to run this. `ghcr.io/peopleforrester/backstage` is public and the Helm
release pulls it anonymously. Build it yourself if you want to change the plugin set, host
the image in your own registry, or see how the image the platform runs is actually made.

## What is here

- `Dockerfile` — the create-app host-build image (Node 24-trixie-slim). Copied into the
  scaffolded app by the build script.
- `app-config.production.yaml` — production config: in-cluster Gitea integration, the
  ArgoCD proxy and plugin config, TechDocs, catalog, guest auth. Secrets and hosts come
  from env vars injected by the Helm release, never hardcoded.
- `overlay/packages/backend/src/index.ts` — backend wiring: the standard new-backend
  system plus `@backstage/plugin-scaffolder-backend-module-gitea`.
- `build-and-push.sh` — scaffolds (once), adds plugins, applies the overlay, builds the
  bundle, builds and pushes `ghcr.io/$GHCR_ORG/backstage:$TAG`.

## Build

```bash
GHCR_ORG=<org> TAG=2026-07-23 ./build-and-push.sh
```

The generated app lands in `backstage-app/` (gitignored). Delete it to rescaffold.

## Runtime config (Helm release)

The `backstage` Application injects these as env vars (from the `gitea-scm-token` Secret
and ArgoCD service account):

- `BACKSTAGE_BASE_URL`
- `GITEA_HOST`, `GITEA_USERNAME`, `GITEA_TOKEN`
- `ARGOCD_AUTH_TOKEN`

Point the release's `image.repository` at `ghcr.io/$GHCR_ORG/backstage` and `image.tag`
at the built tag.

## Manual step: ArgoCD frontend wiring

The Gitea scaffolder actions are wired in the backend overlay and work headless. The
ArgoCD plugin is a frontend plugin: after scaffolding, add its card or tab to
`packages/app/src/components/catalog/EntityPage.tsx` per the plugin README. The proxy and
`argocd` config blocks it needs are already in `app-config.production.yaml`.

## Version note

`CREATE_APP_VERSION` defaults to `latest`. Pin it to the create-app release that ships
the Backstage line in `versions.lock.md` (1.51.x) for a reproducible build, and verify
the backend `index.ts` import set against that version before the freeze.
