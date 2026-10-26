#!/usr/bin/env bash
#
# Stage documentation from initialized Git submodules into their source tree
# under docs/. Set INCLUDE_SUBMODULES=1 to enable this optional behavior.
#
# This script must run from the repository root after prepare-docs.sh, because
# prepare-docs.sh may have copied source directories into docs/ already.

set -euo pipefail

[[ "${INCLUDE_SUBMODULES:-0}" == "1" ]] || exit 0

repo_root="${REPO_ROOT:-$(pwd)}"
if [[ ! -f .gitmodules ]]; then
    echo "No .gitmodules file found; skipping submodule documentation."
    exit 0
fi

while IFS= read -r submodule_path; do
    [[ -n "${submodule_path}" ]] || continue
    [[ "${submodule_path}" == examples/* ]] || continue

    source="${submodule_path}/docs"
    if [[ ! -d "${source}" ]]; then
        echo "Skipping ${submodule_path}: no docs directory"
        continue
    fi

    # prepare-docs.sh may already have copied the submodule into docs/. Remove
    # only its source docs tree, retaining generated JSON pages and other
    # example assets in the same examples tree.
    rm -rf "docs/${submodule_path}/docs"

    target="docs/${submodule_path}"
    mkdir -p "${target}"
    cp -R "${source}/." "${target}/"

    # Keep links within the staged docs tree. Links to source files or
    # READMEs outside that tree are rendered as plain text instead of
    # producing broken-page warnings from Zensical.
    python3 - "${source}" "${target}" <<'PY'
from pathlib import Path
import re
import sys

source_root = Path(sys.argv[1]).resolve()
staged_docs = Path(sys.argv[2]).resolve()
link_pattern = re.compile(r"(?<!\!)\[([^\]]+)\]\(([^)]*)\)")

for page in staged_docs.rglob("*.md"):
    source_page = source_root / page.relative_to(staged_docs)
    text = page.read_text(encoding="utf-8")

    def replace(match: re.Match[str]) -> str:
        label, target = match.groups()
        if target.startswith(("http://", "https://", "mailto:", "#")):
            return match.group(0)
        path = target.split("#", 1)[0].strip()
        if not path.endswith((".md", ".markdown")):
            return match.group(0)
        candidate = (source_page.parent / path).resolve()
        try:
            candidate.relative_to(source_root)
        except ValueError:
            return label
        if not candidate.is_file():
            return label
        return match.group(0)

    updated = link_pattern.sub(replace, text)
    if updated != text:
        page.write_text(updated, encoding="utf-8")
PY

    echo "Staged submodule documentation: ${submodule_path}/docs"
done < <(
    git -C "${repo_root}" submodule foreach --quiet --recursive \
        'printf "%s\\n" "$displaypath"'
)
