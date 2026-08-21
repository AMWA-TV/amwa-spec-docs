#!/usr/bin/env bash
#
# Prepare the docs/ tree for the Zensical site build.
#
# Documentation sources use repository-relative links so they remain useful
# when browsing the source on GitHub. Those paths do not exist in the
# published docs tree, so links that leave docs/ are rewritten to the source
# repository at the ref being published.

set -euo pipefail

REPO_SLUG="${GITHUB_REPOSITORY:?GITHUB_REPOSITORY must be set}"
REF="${BUILD_REF:-${GITHUB_REF_NAME:-main}}"
REPO_URL="https://github.com/${REPO_SLUG}/blob/${REF}"
PUBLIC_DOCS_ROOT="${PUBLIC_DOCS_ROOT:-https://specs.amwa.tv/${REPO_SLUG##*/}}"
TOOLKIT_DIR="${TOOLKIT_DIR:-.}"

# Zensical uses site_url for canonical links. Mike appends the published
# version, so this must remain the unversioned public root.
python3 - "${PUBLIC_DOCS_ROOT%/}/" <<'PY'
from pathlib import Path
import json
import os
import re
import sys

config = Path("zensical.toml")
site_url = sys.argv[1]

if not config.is_file():
    # Historical specification refs predate the shared Zensical migration.
    # Give them a minimal config rather than requiring every old ref to be
    # amended retroactively.
    repository_name = os.environ.get("SITE_NAME", "documentation")
    config.write_text(
        "[project]\n"
        f"site_name = {json.dumps(repository_name)}\n"
        f"site_url = {json.dumps(site_url)}\n\n"
        "[project.extra.version]\n"
        'provider = "mike"\n',
        encoding="utf-8",
    )
else:
    text = config.read_text(encoding="utf-8")
    updated = re.sub(
        r"(?m)^site_url\s*=.*$",
        f'site_url = "{site_url}"',
        text,
        count=1,
    )
    if updated != text:
        config.write_text(updated, encoding="utf-8")
PY

if [[ ! -f README.md ]]; then
    echo "error: README.md not found (run from repo root)" >&2
    exit 1
fi

# Zensical builds from docs/, while these optional source directories live at
# repository root. Stage them into the temporary docs tree for the site build.
for directory in APIs examples; do
    if [[ -d "${directory}" ]]; then
        rm -rf "docs/${directory}"
        cp -R "${directory}" "docs/${directory}"
    fi
done

# docs/README.md is a legacy Jekyll navigation source, not a documentation
# page. The generated index pages and Zensical's implicit navigation replace it.
rm -f docs/README.md

# Render discovered RAML, schema, and example assets and generate their index
# pages. This must happen after root-level assets have been staged into docs/.
python3 "${TOOLKIT_DIR}/scripts/render-doc-assets.py"

# Generate the documentation landing page from README.md. A docs/ directory
# link in README points to the documentation currently being viewed.
sed -E \
    -e 's#\]\(docs/\)#](Overview.md)#g' \
    -e 's#\]\(docs/([^)]+)\)#](\1)#g' \
    -e "s#\]\(\./?LICENSE(\.txt|\.md)?\)#](${REPO_URL}/LICENSE\1)#g" \
    -e "s#\]\(LICENSE(\.txt|\.md)?\)#](${REPO_URL}/LICENSE\1)#g" \
    -e "s#\]\(CONTRIBUTING\.md\)#](${REPO_URL}/CONTRIBUTING.md)#g" \
    -e "s#\]\(SECURITY\.md\)#](${REPO_URL}/SECURITY.md)#g" \
    -e "s#https://github.com/${REPO_SLUG}/blob/[0-9a-f]+/docs/([^)\" ]+)#\1#g" \
    README.md > docs/index.md

echo "Generated docs/index.md from README.md"

# Rewrite links from docs/*.md to repository files. Also remove Jekyll-only
# table-of-contents directives left in older documentation.
shopt -s nullglob
for file in docs/*.md; do
    [[ "${file}" == "docs/index.md" ]] && continue
    sed -i -E \
        -e 's#\]\(\.\./APIs/#](__DOCS_ASSET__/APIs/#g' \
        -e 's#\]\(\.\./examples/#](__DOCS_ASSET__/examples/#g' \
        -e "s#\]\(\.\./([^)]+)\)#](${REPO_URL}/\1)#g" \
        -e 's#\]\(__DOCS_ASSET__/(APIs|examples)/#](../\1/#g' \
        -e "/^\{:\.no_toc\}/,/^[[:space:]]*\{:toc\}/d" \
        "${file}"
done

echo "Rewrote repository-relative links to ${REPO_URL}"
