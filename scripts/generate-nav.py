#!/usr/bin/env python3
"""Translate a legacy docs/README.md navigation into Zensical TOML."""

from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import unquote


DOCS = Path("docs")
NAV_SOURCE = DOCS / "README.md"
CONFIG = Path("zensical.toml")


_LINK = re.compile(r"^(?P<indent>\s*)-\s+\[(?P<label>[^]]+)\]\((?P<target>[^)]+)\)\s*$")
_HEADING = re.compile(r"^###\s+(?P<title>.+?)\s*$")

_GENERATED_TREES = (
    ("APIs", "API Definitions"),
    ("schemas", "JSON Schemas"),
    ("examples", "Examples"),
)


def toml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def target_path(target: str) -> str:
    target = target.split("#", 1)[0].split("?", 1)[0]
    if target.startswith("./"):
        target = target[2:]
    return unquote(target)


def parse_navigation() -> list[tuple[str, list[dict[str, object]]]]:
    sections: list[tuple[str, list[dict[str, object]]]] = []
    current: tuple[str, list[dict[str, object]]] | None = None
    stack: list[tuple[int, list[dict[str, object]]]] = []

    for line in NAV_SOURCE.read_text(encoding="utf-8").splitlines():
        heading = _HEADING.match(line)
        if heading:
            current = (heading.group("title"), [])
            sections.append(current)
            stack = [(-1, current[1])]
            continue

        match = _LINK.match(line)
        if not match:
            continue

        if current is None:
            current = ("Documentation", [])
            sections.append(current)
            stack = [(-1, current[1])]

        indent = len(match.group("indent"))
        path = target_path(match.group("target"))
        if not path.startswith("http"):
            source_path = DOCS / path
            if source_path.is_dir() and (source_path / "index.md").is_file():
                path = f"{path.rstrip('/')}/index.md"
            elif not source_path.is_file():
                print(f"warning: navigation target does not exist: {path}")
                continue

        while stack[-1][0] >= indent:
            stack.pop()

        node: dict[str, object] = {
            "label": match.group("label"),
            "path": path,
            "children": [],
        }
        stack[-1][1].append(node)
        stack.append((indent, node["children"]))

    return sections


def generated_navigation() -> list[tuple[str, str, list[dict[str, object]]]]:
    """Read the indexes generated for root-level API and example assets."""
    generated: list[tuple[str, str, list[dict[str, object]]]] = []
    for directory, display_title in _GENERATED_TREES:
        index = DOCS / directory / "index.md"
        if not index.is_file():
            continue

        nodes: list[dict[str, object]] = []
        for line in index.read_text(encoding="utf-8").splitlines():
            match = _LINK.match(line)
            if not match:
                continue

            path = target_path(match.group("target"))
            if path.startswith("http"):
                continue
            source_path = DOCS / directory / path
            if source_path.is_dir() and (source_path / "index.md").is_file():
                path = f"{path.rstrip('/')}/index.md"
            elif not source_path.is_file():
                print(f"warning: generated navigation target does not exist: {directory}/{path}")
                continue
            nodes.append({"label": match.group("label"), "path": f"{directory}/{path}", "children": []})

        generated.append((directory, display_title, nodes))
    return generated


def add_generated_navigation(
    sections: list[tuple[str, list[object]]],
) -> None:
    """Keep generated asset trees visible when explicit navigation is used."""
    for directory, title, nodes in generated_navigation():
        index_path = f"{directory}/index.md"
        sections.append((title, [index_path, *nodes]))


def render_node(node: dict[str, object], level: int) -> str:
    """Render one Zensical navigation item.

    Zensical represents a page with children as a list whose first item is the
    page path, followed by its child navigation items. Keep each dictionary as
    an inline TOML table, but format the nested list over several lines so the
    generated configuration remains readable.
    """
    indent = "  " * level
    child_indent = "  " * (level + 1)
    label = toml_string(str(node["label"]))
    path = str(node["path"])
    children = node["children"]
    if not children:
        return f'{indent}{{ {label} = {toml_string(path)} }}'

    lines = [f"{indent}{{ {label} = [", f"{child_indent}{toml_string(path)},"]
    for child in children:
        lines.append(render_node(child, level + 1) + ",")
    lines.append(f"{indent}] }}")
    return "\n".join(lines)


def render_nav(sections: list[tuple[str, list[object]]]) -> str:
    lines = ["nav = [", '  "index.md",']
    for title, nodes in sections:
        lines.append(f"  {{ {toml_string(title)} = [")
        for node in nodes:
            if isinstance(node, str):
                lines.append(f"    {toml_string(node)},")
            else:
                lines.append(render_node(node, 2) + ",")
        lines.append("  ] },")
    lines.append("]")
    return "\n".join(lines)


def update_config(nav: str) -> None:
    text = CONFIG.read_text(encoding="utf-8")
    lines = text.splitlines()

    start = next((i for i, line in enumerate(lines) if re.match(r"^\s*nav\s*=\s*\[", line)), None)
    if start is not None:
        end = start
        depth = 0
        while end < len(lines):
            depth += lines[end].count("[") - lines[end].count("]")
            if depth <= 0:
                end += 1
                break
            end += 1
        del lines[start:end]

    project = next((i for i, line in enumerate(lines) if line.strip() == "[project]"), None)
    if project is None:
        raise SystemExit("error: [project] section not found in zensical.toml")

    lines[project + 1:project + 1] = [nav, ""]
    CONFIG.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    if not NAV_SOURCE.is_file():
        return
    sections = parse_navigation()
    add_generated_navigation(sections)
    update_config(render_nav(sections))
    print(f"Generated explicit navigation from {NAV_SOURCE}")


if __name__ == "__main__":
    main()
