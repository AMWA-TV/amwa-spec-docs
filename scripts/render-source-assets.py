#!/usr/bin/env python3
"""Generate foldable source pages for repository documentation assets."""

from __future__ import annotations

import base64
import html
from pathlib import Path


ROOT = Path.cwd()
DOCS = ROOT / "docs"
SOURCE_ROOTS = (ROOT / "examples", ROOT / "manifest")


def language_for(path: Path) -> str | None:
    name = path.name
    if name == "Dockerfile" or name.startswith("Dockerfile"):
        return "dockerfile"
    return {
        ".yaml": "yaml",
        ".yml": "yaml",
        ".py": "python",
        ".sh": "bash",
    }.get(path.suffix.lower())


def render_source_page(source: Path) -> None:
    language = language_for(source)
    if language is None:
        return

    relative = source.relative_to(ROOT)
    output = DOCS / relative.with_suffix(".md")
    encoded = base64.b64encode(source.read_bytes()).decode("ascii")
    filename = html.escape(source.name)

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        f"# `{filename}`\n\n"
        f'<div class="source-viewer" data-source="{encoded}" '
        f'data-language="{language}">\n'
        '  <label class="source-viewer-mode">View: '
        '<select data-source-mode>\n'
        '    <option value="folding" selected>Folding</option>\n'
        '    <option value="raw">Raw</option>\n'
        "  </select></label>\n"
        '  <div class="source-viewer-folding">\n'
        '    <div class="source-viewer-controls" role="group" '
        'aria-label="Source controls">\n'
        '      <button type="button" data-source-action="expand">'
        "Expand all</button>\n"
        '      <button type="button" data-source-action="collapse">'
        "Collapse all</button>\n"
        "    </div>\n"
        '    <div class="source-editor" role="region" '
        'aria-label="Foldable source code"></div>\n'
        "  </div>\n"
        '  <pre class="source-viewer-raw" hidden><code></code></pre>\n'
        "</div>\n",
        encoding="utf-8",
    )


def main() -> None:
    for source_root in SOURCE_ROOTS:
        if not source_root.is_dir():
            continue
        for source in sorted(path for path in source_root.rglob("*") if path.is_file()):
            render_source_page(source)


if __name__ == "__main__":
    main()
