#!/usr/bin/env python3
"""Render repository API, schema, and example assets for Zensical.

The source repositories keep these assets outside docs/. Zensical only builds
from docs/, so this script creates a temporary documentation tree and derives
all index pages by discovery rather than maintaining lists in configuration.
"""

from __future__ import annotations

import base64
import json
import os
import re
import shutil
import subprocess
import textwrap
from pathlib import Path
from typing import Any


ROOT = Path.cwd()
DOCS = ROOT / "docs"
API_SOURCE = ROOT / "APIs"
EXAMPLE_SOURCE = ROOT / "examples"
API_DOCS = DOCS / "APIs"
SCHEMA_DOCS = DOCS / "schemas"
EXAMPLE_DOCS = DOCS / "examples"


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")



def render_json(value: Any) -> str:
    """Render JSON with the same foldable source viewer used for YAML assets."""
    source = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    encoded = base64.b64encode(source.encode("utf-8")).decode("ascii")
    return (
        f'<div class="json-viewer" data-source="{encoded}" data-language="json">\n'
        '  <label class="source-viewer-mode">View: '
        '<select data-source-mode>\n'
        '    <option value="folding" selected>Folding</option>\n'
        '    <option value="raw">Raw</option>\n'
        "  </select></label>\n"
        '  <div class="source-viewer-folding">\n'
        '    <div class="source-viewer-controls" role="group" '
        'aria-label="JSON source controls">\n'
        '      <button type="button" data-source-action="expand">'
        "Expand all</button>\n"
        '      <button type="button" data-source-action="collapse">'
        "Collapse all</button>\n"
        "    </div>\n"
        '    <div class="source-editor" role="region" '
        'aria-label="Foldable JSON source"></div>\n'
        "  </div>\n"
        '  <pre class="source-viewer-raw" hidden><code></code></pre>\n'
        "</div>\n"
    )


def render_json_js() -> str:
    return r'''(() => {
  "use strict";

  function decodeSource(encoded) {
    const binary = window.atob(encoded);
    const bytes = Uint8Array.from(binary, character => character.charCodeAt(0));
    return new TextDecoder().decode(bytes);
  }

  function addToken(container, text, className) {
    if (!text) return;
    const token = document.createElement("span");
    token.className = className;
    token.textContent = text;
    container.appendChild(token);
  }

  function renderCode(line) {
    const code = document.createElement("span");
    code.className = "source-editor-code";
    const pattern = /("(?:[^"\\]|\\.)*")|(-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?)|(\b(?:true|false|null)\b)|([{}\[\],:])/g;
    let position = 0;
    let match;

    while ((match = pattern.exec(line)) !== null) {
      addToken(code, line.slice(position, match.index), "");
      const tokenClass = match[1]
        ? "source-token-string"
        : match[2]
          ? "source-token-number"
          : match[3]
            ? "source-token-boolean"
            : "source-token-punctuation";
      addToken(code, match[0], tokenClass);
      position = pattern.lastIndex;
    }
    addToken(code, line.slice(position), "");
    return code;
  }

  function indentation(line) {
    const whitespace = line.match(/^[ \t]*/)[0];
    return whitespace.replace(/\t/g, "  ").length;
  }

  function foldEnd(lines, start) {
    if (lines[start].trim() === "") return null;
    const currentIndent = indentation(lines[start]);
    let next = start + 1;
    while (next < lines.length && lines[next].trim() === "") next += 1;
    if (next >= lines.length || indentation(lines[next]) <= currentIndent) return null;

    let end = next;
    while (end < lines.length) {
      if (lines[end].trim() !== "" && indentation(lines[end]) <= currentIndent) break;
      end += 1;
    }
    return end;
  }

  function createLine(lines, number, end) {
    const row = document.createElement("div");
    row.className = "source-editor-line";
    row.dataset.line = String(number);

    const gutter = document.createElement("span");
    gutter.className = "source-editor-gutter";
    if (end !== null) {
      const toggle = document.createElement("button");
      toggle.className = "source-editor-fold-toggle";
      toggle.type = "button";
      toggle.textContent = "⌄";
      toggle.setAttribute("aria-label", "Collapse lines");
      toggle.setAttribute("aria-expanded", "true");
      toggle.dataset.foldEnd = String(end);
      gutter.appendChild(toggle);
    } else {
      const spacer = document.createElement("span");
      spacer.className = "source-editor-fold-spacer";
      gutter.appendChild(spacer);
    }

    const lineNumber = document.createElement("span");
    lineNumber.className = "source-editor-line-number";
    lineNumber.textContent = String(number);
    gutter.appendChild(lineNumber);
    row.append(gutter, renderCode(lines[number - 1]));
    return row;
  }

  function setFoldState(editor, row, collapsed) {
    const toggle = row.querySelector(".source-editor-fold-toggle");
    if (!toggle) return;
    row.toggleAttribute("data-collapsed", collapsed);
    toggle.textContent = collapsed ? "›" : "⌄";
    toggle.setAttribute("aria-expanded", String(!collapsed));
    toggle.setAttribute("aria-label", collapsed ? "Expand lines" : "Collapse lines");

    const start = Number(row.dataset.line);
    const end = Number(toggle.dataset.foldEnd);
    editor.querySelectorAll(".source-editor-line").forEach(child => {
      const number = Number(child.dataset.line);
      if (number > start && number <= end) child.hidden = collapsed;
    });
  }

  function initializeViewer(viewer) {
    const editor = viewer.querySelector(".source-editor");
    const source = decodeSource(viewer.dataset.source);
    const lines = source.replace(/\r/g, "").split("\n");
    const foldEnds = lines.map((line, index) => foldEnd(lines, index));
    const rows = lines.map((line, index) => createLine(lines, index + 1, foldEnds[index]));
    rows.forEach(row => editor.appendChild(row));

    editor.querySelectorAll(".source-editor-fold-toggle").forEach(toggle => {
      toggle.addEventListener("click", () => {
        const row = toggle.closest(".source-editor-line");
        setFoldState(editor, row, !row.hasAttribute("data-collapsed"));
      });
    });

    viewer.querySelector('[data-source-action="expand"]').addEventListener("click", () => {
      editor.querySelectorAll(".source-editor-line").forEach(row => setFoldState(editor, row, false));
    });
    viewer.querySelector('[data-source-action="collapse"]').addEventListener("click", () => {
      editor.querySelectorAll(".source-editor-line").forEach(row => setFoldState(editor, row, row.querySelector(".source-editor-fold-toggle") !== null));
    });

    const rawView = viewer.querySelector(".source-viewer-raw");
    rawView.querySelector("code").textContent = source;
    const foldingView = viewer.querySelector(".source-viewer-folding");
    viewer.querySelector("[data-source-mode]").addEventListener("change", event => {
      const folding = event.target.value === "folding";
      foldingView.hidden = !folding;
      rawView.hidden = folding;
    });
  }

  function initializeViewers() {
    document.querySelectorAll(".json-viewer").forEach(viewer => {
      if (viewer.dataset.initialized === "true") return;
      try {
        initializeViewer(viewer);
        viewer.dataset.initialized = "true";
      } catch (error) {
        const message = document.createElement("p");
        message.textContent = "Unable to render this JSON source file.";
        viewer.appendChild(message);
        console.error("Unable to initialize JSON source viewer", error);
      }
    });
  }

  if (typeof document$ !== "undefined") {
    document$.subscribe(initializeViewers);
  } else if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initializeViewers);
  } else {
    initializeViewers();
  }
})();
'''


def render_json_css() -> str:
    return """.json-viewer {
  margin: 1rem 0;
  overflow-x: auto;
}

.source-viewer-mode {
  display: inline-block;
  margin: 0 0 0.35rem;
}

.source-viewer-mode select {
  margin-left: 0.25rem;
}

.source-viewer-controls {
  display: flex;
  gap: 0.35rem;
  margin: 0 0 0.35rem;
}

.source-viewer-controls button {
  border: 1px solid var(--md-default-fg-color--lightest);
  border-radius: 0.2rem;
  background: var(--md-default-bg-color);
  color: var(--md-default-fg-color);
  cursor: pointer;
  padding: 0.15rem 0.45rem;
}

.source-viewer-controls button:hover,
.source-viewer-mode select:hover {
  background: var(--md-default-fg-color--lightest);
}

.source-editor,
.source-viewer-raw {
  border: 1px solid var(--md-default-fg-color--lightest);
  border-radius: 0.2rem;
  background: var(--md-code-bg-color, var(--md-default-bg-color));
  color: var(--md-code-fg-color, var(--md-typeset-color));
  font-family: var(--md-code-font-family, monospace);
  font-size: 0.8rem;
  line-height: 1.35;
  margin: 0;
  overflow-x: auto;
  padding: 0.35rem 0;
}

.source-viewer-raw code {
  white-space: pre;
}

.source-editor-line {
  min-height: 1.35em;
  padding: 0 0.5rem 0 0;
  white-space: pre;
}

.source-editor-line[hidden] {
  display: none;
}

.source-editor-gutter {
  display: inline-flex;
  align-items: center;
  width: 4.5em;
}

.source-editor-fold-toggle,
.source-editor-fold-spacer {
  display: inline-block;
  width: 1.5em;
}

.source-editor-fold-toggle {
  border: 0;
  background: transparent;
  color: var(--md-default-fg-color--light);
  cursor: pointer;
  font: inherit;
  line-height: 1;
  padding: 0;
  text-align: center;
}

.source-editor-fold-toggle:hover {
  color: var(--md-typeset-color);
}

.source-editor-line-number {
  color: var(--md-default-fg-color--light);
  display: inline-block;
  padding-right: 0.75em;
  text-align: right;
  user-select: none;
  width: 2.5em;
}

.source-editor-code {
  color: var(--md-code-fg-color, var(--md-typeset-color));
}

.source-editor-line[data-collapsed] .source-editor-code::after {
  color: var(--md-default-fg-color--light);
  content: " ...";
}

.source-token-string {
  color: var(--md-code-hl-string-color, var(--md-typeset-color));
}

.source-token-number,
.source-token-boolean {
  color: var(--md-code-hl-number-color, var(--md-typeset-color));
}

.source-token-punctuation {
  color: var(--md-typeset-color);
}

.json-viewer .source-viewer-folding[hidden],
.json-viewer .source-viewer-raw[hidden] {
  display: none;
}
"""


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def resolve_reference(value: Any, schema_dir: Path, stack: tuple[str, ...] = ()) -> Any:
    """Resolve local JSON Schema file references, preserving external refs."""
    if isinstance(value, list):
        return [resolve_reference(item, schema_dir, stack) for item in value]
    if not isinstance(value, dict):
        return value

    reference = value.get("$ref")
    if isinstance(reference, str) and not reference.startswith("#"):
        target_name, _, fragment = reference.partition("#")
        target = (schema_dir / target_name).resolve()
        if target.exists() and target.is_file():
            key = str(target)
            if key not in stack:
                target_value = load_json(target)
                if fragment:
                    for part in fragment.lstrip("/").split("/"):
                        target_value = target_value[part.replace("~1", "/").replace("~0", "~")]
                return resolve_reference(target_value, schema_dir, (*stack, key))

    return {key: resolve_reference(item, schema_dir, stack) for key, item in value.items()}


def render_schemas() -> None:
    source = API_SOURCE / "schemas"
    if not source.is_dir():
        return

    schema_paths = sorted(source.rglob("*.json"))
    if not schema_paths:
        return
    resolved_dir = SCHEMA_DOCS / "resolved"
    raw_entries: list[tuple[str, str]] = []

    for schema_path in schema_paths:
        relative = schema_path.relative_to(source)
        # The current NMOS layout is flat; preserve subdirectories if a future
        # template adds them.
        raw_json = SCHEMA_DOCS / relative
        raw_md = raw_json.with_suffix(".md")
        raw_value = load_json(schema_path)
        raw_json.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(schema_path, raw_json)
        resolved_value = resolve_reference(raw_value, source)

        raw_entries.append((relative.with_suffix(".md").as_posix(), relative.stem))
        resolved_json = resolved_dir / relative
        resolved_json.parent.mkdir(parents=True, exist_ok=True)
        resolved_json.write_text(json.dumps(resolved_value, indent=2) + "\n", encoding="utf-8")


        raw_tab = textwrap.indent(render_json(raw_value).rstrip(), "    ")
        resolved_tab = textwrap.indent(render_json(resolved_value).rstrip(), "    ")
        write(
            raw_md,
            f"# {relative.stem}\n\n"
            "=== \"With refs\"\n\n"
            f"{raw_tab}\n\n"
            "=== \"Resolved\"\n\n"
            f"{resolved_tab}\n",
        )

    lines = ["# JSON Schemas", ""]
    for relative, title in raw_entries:
        lines.append(f"- [{title}]({relative})")
    write(SCHEMA_DOCS / "index.md", "\n".join(lines) + "\n")



def render_examples() -> None:
    if not EXAMPLE_SOURCE.is_dir():
        return

    example_paths = sorted(EXAMPLE_SOURCE.rglob("*.json"))
    if not example_paths:
        return

    entries: list[tuple[str, str]] = []
    for example_path in example_paths:
        relative = example_path.relative_to(EXAMPLE_SOURCE)
        output_json = EXAMPLE_DOCS / relative
        output_md = output_json.with_suffix(".md")
        shutil.copy2(example_path, output_json)
        entries.append((relative.with_suffix(".md").as_posix(), relative.name))
        write(
            output_md,
            f"# {relative.name}\n\n"
            + render_json(load_json(example_path)),
        )

    lines = ["# Examples", ""]
    for relative, title in entries:
        lines.append(f"- [{title}]({relative})")
    write(EXAMPLE_DOCS / "index.md", "\n".join(lines) + "\n")


def raml_overview(path: Path) -> str:
    """Extract the RAML documentation entry titled Overview."""
    lines = path.read_text(encoding="utf-8").splitlines()
    overview_title = re.compile(r"^(\s*)-\s+title:\s*['\"]?Overview['\"]?\s*$")

    for index, line in enumerate(lines):
        title_match = overview_title.match(line)
        if not title_match:
            continue
        title_indent = len(title_match.group(1))
        for content_index, content_line in enumerate(lines[index + 1 :], start=index + 1):
            if content_line.strip() and len(content_line) - len(content_line.lstrip()) <= title_indent:
                break
            content_match = re.match(r"^(\s*)content:\s*(.*)$", content_line)
            if not content_match:
                continue
            value = content_match.group(2).strip()
            if value and value not in {"|", ">"}:
                return value.strip("'\"").strip()

            content_indent = len(content_match.group(1))
            content_lines: list[str] = []
            for body_line in lines[content_index + 1 :]:
                if body_line.strip() and len(body_line) - len(body_line.lstrip()) <= content_indent:
                    break
                content_lines.append(body_line)
            return textwrap.dedent("\n".join(content_lines)).strip()
    return ""


def render_apis() -> None:
    if not API_SOURCE.is_dir():
        return

    raml_paths = sorted(API_SOURCE.rglob("*.raml"))
    if not raml_paths:
        return

    entries: list[tuple[str, str]] = []
    renderer = os.environ.get("RAML2HTML_BIN", "")
    for raml_path in raml_paths:
        relative = raml_path.relative_to(API_SOURCE)
        output = API_DOCS / relative.with_suffix(".html")
        output_md = output.with_suffix(".md")
        output.parent.mkdir(parents=True, exist_ok=True)
        if not renderer:
            raise RuntimeError(
                "RAML files were found but RAML2HTML_BIN is not set; "
                "install raml2html before rendering documentation"
            )
        subprocess.run(
            [renderer, "--input", str(raml_path), "--output", str(output), "--pretty"],
            cwd=ROOT,
            check=True,
        )
        overview = raml_overview(raml_path)
        overview_text = f"{overview}\n\n" if overview else ""
        write(
            output_md,
            f"# {relative.stem}\n\n"
            f"{overview_text}"
            f"[Open {relative.stem} API documentation]({output.name})\n",
        )
        entries.append((relative.with_suffix(".md").as_posix(), relative.stem))

    lines = ["# APIs", ""]
    for relative, title in entries:
        lines.append(f"- [{title}]({relative})")
    write(API_DOCS / "index.md", "\n".join(lines) + "\n")


def main() -> None:
    # README.md files in these source trees are legacy navigation stubs. The
    # generated index pages below are the actual Zensical section indexes.
    for tree in (API_DOCS, EXAMPLE_DOCS):
        if tree.is_dir():
            for readme in tree.rglob("README.md"):
                readme.unlink()
    render_apis()
    render_schemas()
    render_examples()
    write(DOCS / "stylesheets" / "extra.css", render_json_css())
    write(DOCS / "javascripts" / "json-viewer.js", render_json_js())


if __name__ == "__main__":
    main()
