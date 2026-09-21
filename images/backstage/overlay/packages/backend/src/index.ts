// ABOUTME: Backstage backend entrypoint for the platform image. Standard new-backend
// ABOUTME: system wiring plus the Gitea scaffolder module for the golden path.
//
// Copied over the scaffolded packages/backend/src/index.ts by build-and-push.sh. The
// ArgoCD integration is a frontend plugin over the proxy (see app-config and README),
// so it needs no backend module here. Verify imports against the pinned Backstage
// version if create-app changes the default set.
import { createBackend } from '@backstage/backend-defaults';

const backend = createBackend();

// Core
backend.add(import('@backstage/plugin-app-backend'));
backend.add(import('@backstage/plugin-proxy-backend'));

// Catalog
backend.add(import('@backstage/plugin-catalog-backend'));
backend.add(
  import('@backstage/plugin-catalog-backend-module-scaffolder-entity-model'),
);

// Scaffolder plus the Gitea publish/read actions the golden path uses
backend.add(import('@backstage/plugin-scaffolder-backend'));
backend.add(import('@backstage/plugin-scaffolder-backend-module-gitea'));

// TechDocs
backend.add(import('@backstage/plugin-techdocs-backend'));

// Auth (guest provider for a local build; replace for a real deployment)
backend.add(import('@backstage/plugin-auth-backend'));
backend.add(import('@backstage/plugin-auth-backend-module-guest-provider'));

backend.start();
