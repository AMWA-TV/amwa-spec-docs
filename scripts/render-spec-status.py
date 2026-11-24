"""Add the spec.yml status to the generated documentation landing page."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml

_STATUS_LINE = re.compile(r"^\*\*Status:\*\*.*$")
_TITLE_LINE = re.compile(r"^#\s+.+$")


def read_status(source: Path, metadata_dir: Path | None = None) -> str | None:
    """Read status from this ref, falling back to current-ref metadata."""
    candidates = [source]
    if metadata_dir is not None:
        candidates.append(metadata_dir / source.name)

    seen: set[Path] = set()
    for candidate in candidates:
        candidate = candidate.resolve()
        if candidate in seen:
            continue
        seen.add(candidate)
        if not candidate.is_file():
            continue

        data: Any = yaml.safe_load(candidate.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            status = data.get("status")
            if status is not None and str(status).strip():
                return str(status).strip()
    return None


def add_status(markdown: str, status: str) -> str:
    """Place or update the status line immediately below the first H1."""
    lines = markdown.splitlines()
    title_index = next(
        (index for index, line in enumerate(lines) if _TITLE_LINE.match(line)),
        None,
    )
    if title_index is None:
        raise ValueError("documentation landing page has no level-one title")

    remainder = lines[title_index + 1 :]
    while remainder and not remainder[0].strip():
        remainder.pop(0)
    if remainder and _STATUS_LINE.match(remainder[0]):
        remainder.pop(0)
        while remainder and not remainder[0].strip():
            remainder.pop(0)

    updated = lines[: title_index + 1] + ["", f"**Status:** {status}", ""] + remainder
    rendered = "\n".join(updated)
    return rendered + ("\n" if markdown.endswith("\n") else "")


def main() -> None:
    source = Path("spec.yml")
    metadata_dir_value = os.environ.get("METADATA_DIR")
    metadata_dir = Path(metadata_dir_value) if metadata_dir_value else None
    status = read_status(source, metadata_dir)
    if status is None:
        print("Skipping status: no status found in spec.yml metadata")
        return

    front_page = Path("docs/index.md")
    if not front_page.is_file():
        raise SystemExit(f"error: documentation landing page not found: {front_page}")
    front_page.write_text(
        add_status(front_page.read_text(encoding="utf-8"), status),
        encoding="utf-8",
    )
    print(f"Added spec.yml status to {front_page}: {status}")


if __name__ == "__main__":
    main()
