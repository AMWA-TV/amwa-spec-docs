#!/usr/bin/env bash
#
# Build and serve the current working tree without modifying it.
#
# Usage:
#   ../amwa-spec-docs/scripts/local-render.sh
#
# The temporary copy is removed when the preview server exits. Set
# KEEP_RENDER=1 to keep it for inspection.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOOLKIT_DIR="${SCRIPT_DIR}/.."
REPO_ROOT="${REPO_ROOT:-$(pwd)}"
PORT="${PORT:-8000}"
REF="${BUILD_REF:-$(git -C "${REPO_ROOT}" branch --show-current)}"
REF="${REF:-local}"
REPO_NAME="$(basename "${REPO_ROOT}")"
VENV_DIR="${VENV_DIR:-${TMPDIR:-/tmp}/amwa-spec-docs-venv}"
RAML_DIR="${RAML_DIR:-${TMPDIR:-/tmp}/amwa-spec-docs-raml2html}"
WORK_DIR="$(mktemp -d "${TMPDIR:-/tmp}/amwa-spec-docs-render.XXXXXX")"
KEEP_RENDER="${KEEP_RENDER:-0}"

cleanup() {
    if [[ "${KEEP_RENDER}" == "1" ]]; then
        echo "Keeping temporary render at: ${WORK_DIR}"
    else
        rm -rf "${WORK_DIR}"
    fi
}
trap cleanup EXIT

if ! command -v rsync >/dev/null 2>&1; then
    echo "error: rsync is required" >&2
    exit 1
fi

if [[ ! -x "${VENV_DIR}/bin/zensical" ]]; then
    echo "Creating/installing local Python tools in ${VENV_DIR}"
    python3 -m venv "${VENV_DIR}"
    "${VENV_DIR}/bin/pip" install --upgrade pip
    "${VENV_DIR}/bin/pip" install zensical
fi

if [[ ! -x "${RAML_DIR}/node_modules/.bin/raml2html" ]]; then
    if ! command -v npm >/dev/null 2>&1; then
        echo "error: npm is required to render RAML files" >&2
        exit 1
    fi
    echo "Installing local RAML renderer in ${RAML_DIR}"
    npm install --prefix "${RAML_DIR}" raml2html
fi

echo "Copying current working tree to ${WORK_DIR}"
rsync -a \
    --exclude '.git/' \
    --exclude 'site/' \
    --exclude '.render-zensical/' \
    "${REPO_ROOT}/" "${WORK_DIR}/"

cd "${WORK_DIR}"
export BUILD_REF="${REF}"
export GITHUB_REPOSITORY="${GITHUB_REPOSITORY:-AMWA-TV/${REPO_NAME}}"
# Local Zensical serves at the site root, so do not append BUILD_REF here.
export DOCS_URL="${DOCS_URL:-http://127.0.0.1:${PORT}}"
export PUBLIC_DOCS_ROOT="${PUBLIC_DOCS_ROOT:-${DOCS_URL}}"
export RAML2HTML_BIN="${RAML_DIR}/node_modules/.bin/raml2html"
export TOOLKIT_DIR

bash "${TOOLKIT_DIR}/scripts/prepare-docs.sh"
"${VENV_DIR}/bin/zensical" build --clean

echo ""
echo "Serving ${WORK_DIR}/site at http://127.0.0.1:${PORT}"
echo "Press Ctrl-C to stop and remove the temporary copy."
echo ""

# Pass custom serve options through ZENSICAL_SERVE_ARGS if needed. The
# default keeps the preview port aligned with DOCS_URL.
SERVE_ARGS="${ZENSICAL_SERVE_ARGS:---dev-addr 127.0.0.1:${PORT}}"
# shellcheck disable=SC2086
exec "${VENV_DIR}/bin/zensical" serve ${SERVE_ARGS}
