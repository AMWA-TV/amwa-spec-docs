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

WATCH_PID=""

cleanup() {
    if [[ -n "${WATCH_PID}" ]]; then
        kill "${WATCH_PID}" 2>/dev/null || true
        wait "${WATCH_PID}" 2>/dev/null || true
    fi
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
    if [[ ! -x "${VENV_DIR}/bin/python" || ! -x "${VENV_DIR}/bin/pip" ]]; then
        rm -rf "${VENV_DIR}"
        python3 -m venv "${VENV_DIR}"
    fi
    "${VENV_DIR}/bin/python" -m pip install --upgrade pip
    "${VENV_DIR}/bin/python" -m pip install zensical pyyaml
fi

if [[ ! -x "${RAML_DIR}/node_modules/.bin/raml2html" ]]; then
    if ! command -v npm >/dev/null 2>&1; then
        echo "error: npm is required to render RAML files" >&2
        exit 1
    fi
    echo "Installing local RAML renderer in ${RAML_DIR}"
    npm install --prefix "${RAML_DIR}" raml2html
fi

build_site() {
    local build_dir="${WORK_DIR}/build"
    rm -rf "${build_dir}"
    mkdir -p "${build_dir}"

    echo "Building documentation..."
    if ! rsync -a \
        --exclude '.git/' \
        --exclude 'site/' \
        --exclude '.render-zensical/' \
        "${REPO_ROOT}/" "${build_dir}/"; then
        echo "Source copy failed." >&2
        return 1
    fi

    if ! (
        cd "${build_dir}"
        export BUILD_REF="${REF}"
        export GITHUB_REPOSITORY="${GITHUB_REPOSITORY:-AMWA-TV/${REPO_NAME}}"
        # The static preview serves the built site at its root, so do not
        # append BUILD_REF here.
        export DOCS_URL="${DOCS_URL:-http://127.0.0.1:${PORT}}"
        export PUBLIC_DOCS_ROOT="${PUBLIC_DOCS_ROOT:-${DOCS_URL}}"
        export RAML2HTML_BIN="${RAML_DIR}/node_modules/.bin/raml2html"
        export TOOLKIT_DIR

        bash "${TOOLKIT_DIR}/scripts/prepare-docs.sh"
        "${VENV_DIR}/bin/zensical" build --clean
        python3 "${TOOLKIT_DIR}/scripts/render-spec-json.py"
        python3 "${TOOLKIT_DIR}/scripts/render-search-index.py"
    ); then
        echo "Documentation build failed." >&2
        return 1
    fi
    if [[ ! -d "${build_dir}/site" ]]; then
        echo "Documentation build did not produce a site directory." >&2
        return 1
    fi

    # Keep the server live while a rebuild is in progress, then replace the
    # served tree in one operation so requests never see a partial build.
    rm -rf "${WORK_DIR}/site.next"
    mv "${build_dir}/site" "${WORK_DIR}/site.next"
    rm -rf "${WORK_DIR}/site"
    mv "${WORK_DIR}/site.next" "${WORK_DIR}/site"
    rm -rf "${build_dir}"
}

snapshot_sources() {
    python3 - "${REPO_ROOT}" <<'PY'
import hashlib
import os
import sys

root = os.path.abspath(sys.argv[1])
skip = {".git", ".cache", ".render-zensical", ".venv", "site"}
entries = []
for directory, directories, files in os.walk(root):
    directories[:] = sorted(name for name in directories if name not in skip)
    for name in sorted(files):
        path = os.path.join(directory, name)
        try:
            stat = os.stat(path)
        except FileNotFoundError:
            continue
        relative = os.path.relpath(path, root)
        entries.append(f"{relative}\0{stat.st_size}\0{stat.st_mtime_ns}")
print(hashlib.sha256("\n".join(entries).encode()).hexdigest())
PY
}

build_site

watch_sources() {
    local previous current
    previous="$(snapshot_sources)"
    while sleep 1; do
        current="$(snapshot_sources)"
        if [[ "${current}" != "${previous}" ]]; then
            echo "Source changes detected; rebuilding..."
            if build_site; then
                echo "Rebuild complete."
            else
                echo "Rebuild failed; keeping the previous site." >&2
            fi
            previous="${current}"
        fi
    done
}

watch_sources &
WATCH_PID="$!"

echo ""
echo "Serving ${WORK_DIR}/site at http://127.0.0.1:${PORT}"
echo "Watching ${REPO_ROOT} for changes. Press Ctrl-C to stop."
echo ""

# Zensical serve rebuilds the site and would remove the post-build spec.json.
# Serve the completed output directly so generated metadata remains available.
python3 -m http.server "${PORT}" --bind 127.0.0.1 --directory "${WORK_DIR}/site"
