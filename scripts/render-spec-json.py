#!/usr/bin/env python3
"""Publish spec.yml metadata and the README intro as site/spec.json."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import yaml


_INTRO_HEADINGS = {
    "What does it do?": "what_does_it_do",
    "Why does it matter?": "why_does_it_matter",
    "How does it work?": "how_does_it_work",
}


def readme_intro(readme: Path) -> dict[str, list[str]]:
    """Extract the standard introductory bullet lists from README.md."""

    if not readme.is_file():
        return {}

    text = readme.read_text(encoding="utf-8")
    if "<!-- INTRO-START -->" in text:
        text = text.split("<!-- INTRO-START -->", 1)[1]
    if "<!-- INTRO-END -->" in text:
        text = text.split("<!-- INTRO-END -->", 1)[0]

    intro: dict[str, list[str]] = {}
    current: str | None = None
    for line in text.splitlines():
        heading = re.match(r"^###\s+(.+?)\s*$", line)
        if heading:
            current = _INTRO_HEADINGS.get(heading.group(1))
            if current:
                intro[current] = []
            continue
        bullet = re.match(r"^\s*-\s+(.+?)\s*$", line)
        if current and bullet:
            intro[current].append(bullet.group(1))

    return {key: values for key, values in intro.items() if values}


def render_spec_json(source: Path, destination: Path) -> None:
    data: Any = yaml.safe_load(source.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise TypeError(f"{source} must contain a YAML mapping")

    intro = readme_intro(source.parent / "README.md")
    if intro:
        data["intro"] = intro

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", nargs="?", type=Path, default=Path("spec.yml"))
    parser.add_argument(
        "destination", nargs="?", type=Path, default=Path("site/spec.json")
    )
    args = parser.parse_args()
    render_spec_json(args.source, args.destination)
    print(f"Wrote {args.destination}")


if __name__ == "__main__":
    main()
