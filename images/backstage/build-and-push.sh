#!/usr/bin/env bash
# ABOUTME: Scaffolds the Backstage app, overlays this platform's config and plugins,
# ABOUTME: builds the backend bundle, and pushes the image to GHCR.
set -euo pipefail

# The scaffold pins yarn 4 via Corepack; let it download non-interactively.
export COREPACK_ENABLE_DOWNLOAD_PROMPT=0

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly SCRIPT_DIR

GHCR_ORG="${GHCR_ORG:-}"
TAG="${TAG:-}"
# create-app version that ships the pinned Backstage line (see versions.lock: 1.51.x).
CREATE_APP_VERSION="${CREATE_APP_VERSION:-latest}"
readonly APP_DIR="${SCRIPT_DIR}/backstage-app"   # generated, gitignored

log() { printf '%s\n' "$*" >&2; }

usage() {
    cat >&2 <<EOF
Usage: GHCR_ORG=<org> TAG=<tag> [CREATE_APP_VERSION=<ver>] ${0##*/}

Scaffolds (once) and builds the Backstage image this platform runs, then pushes
ghcr.io/\${GHCR_ORG}/backstage:\${TAG}. Requires node, yarn, npx, docker.
The generated app lives in ${APP_DIR##*/}/ (gitignored); delete it to rescaffold.
EOF
    exit 2
}

require_tools() {
    local t missing=0
    for t in node yarn npx docker; do
        command -v "${t}" >/dev/null 2>&1 || { log "missing tool: ${t}"; missing=1; }
    done
    [[ "${missing}" -eq 0 ]] || exit 1

    # The scaffolder dep isolated-vm fails to compile on Node 25+. Build under Node 24.
    local node_major
    node_major="$(node -p 'process.versions.node.split(".")[0]')"
    if [[ "${node_major}" -ge 25 ]]; then
        log "node ${node_major} is too new: isolated-vm (scaffolder backend) fails to build."
        log "Build under Node 24, e.g.:"
        log "  PATH=\"\$(brew --prefix node@24)/bin:\${PATH}\" ${0##*/}"
        exit 1
    fi
}

scaffold() {
    if [[ -d "${APP_DIR}" ]]; then
        log "reusing existing scaffold at ${APP_DIR}"
        return
    fi
    log "scaffolding Backstage app (create-app ${CREATE_APP_VERSION})"
    # create-app has no --name flag; the name only comes from an interactive prompt, so
    # feed it on stdin (no TTY in a scripted/background run).
    printf 'backstage\n' | npx "@backstage/create-app@${CREATE_APP_VERSION}" \
        --path "${APP_DIR}" --skip-install
}

add_plugins() {
    log "adding plugins"
    # Backend: the Gitea scaffolder actions used by the golden path.
    yarn --cwd "${APP_DIR}" workspace backend add \
        @backstage/plugin-scaffolder-backend-module-gitea
    # Frontend: the ArgoCD plugin (UI wiring is documented in README.md).
    yarn --cwd "${APP_DIR}" workspace app add @roadiehq/backstage-plugin-argo-cd
}

overlay() {
    log "applying overlay (backend index + config + Dockerfile)"
    cp -f "${SCRIPT_DIR}/overlay/packages/backend/src/index.ts" \
          "${APP_DIR}/packages/backend/src/index.ts"
    cp -f "${SCRIPT_DIR}/app-config.production.yaml" "${APP_DIR}/app-config.production.yaml"
    cp -f "${SCRIPT_DIR}/Dockerfile" "${APP_DIR}/packages/backend/Dockerfile"
}

build_bundle() {
    log "installing and building the backend bundle"
    yarn --cwd "${APP_DIR}" install --immutable
    yarn --cwd "${APP_DIR}" tsc
    yarn --cwd "${APP_DIR}" build:backend
}

build_image() {
    local image="ghcr.io/${GHCR_ORG}/backstage:${TAG}"
    log "building ${image}"
    docker build -t "${image}" -f "${APP_DIR}/packages/backend/Dockerfile" "${APP_DIR}"
    log "pushing ${image}"
    docker push "${image}"
    log "done: ${image}"
}

main() {
    [[ -n "${GHCR_ORG}" && -n "${TAG}" ]] || usage
    require_tools
    scaffold
    add_plugins
    overlay
    build_bundle
    build_image
}

main "$@"
