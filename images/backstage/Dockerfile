# ABOUTME: Host-build Dockerfile for the Backstage image this platform runs. Expects the
# ABOUTME: create-app repo to be built (yarn build:backend) before docker build.
#
# This is the create-app host-build pattern: the bundle is produced on the host, the
# image just unpacks and runs it. Build context is the generated app repo root.
FROM node:24-trixie-slim

ENV NODE_ENV=production
WORKDIR /app

# isolate-vm (used by the scaffolder backend) and better-sqlite3 need a toolchain.
RUN apt-get update && apt-get install -y --no-install-recommends \
      python3 g++ build-essential libsqlite3-dev ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Yarn 4 config and the pinned release binary. The scaffold sets yarnPath to this binary,
# but the slim image's built-in yarn is 1.22 and ignores yarnPath, so copy both and invoke
# the pinned yarn 4 directly for the production install.
COPY .yarnrc.yml ./
COPY .yarn/releases ./.yarn/releases

# Skeleton: package.json files and yarn config, so the production install can resolve.
COPY yarn.lock package.json packages/backend/dist/skeleton.tar.gz ./
RUN tar xzf skeleton.tar.gz && rm skeleton.tar.gz

RUN --mount=type=cache,target=/home/node/.cache/yarn \
    node .yarn/releases/yarn-4.13.0.cjs workspaces focus --all --production

# The built backend bundle plus the config files.
COPY packages/backend/dist/bundle.tar.gz app-config.yaml app-config.production.yaml ./
RUN tar xzf bundle.tar.gz && rm bundle.tar.gz

USER node
ENTRYPOINT ["node", "packages/backend", \
            "--config", "app-config.yaml", \
            "--config", "app-config.production.yaml"]
