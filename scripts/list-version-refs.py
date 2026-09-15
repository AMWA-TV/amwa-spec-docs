#!/usr/bin/env python3
"""Select publishable branches and tags for a versioned documentation site.

The input is the tabular output of ``git ls-remote`` or an equivalent source:

    <object-id>\trefs/heads/v1.2.x
    <object-id>\trefs/tags/v1.2.0

The matching rules intentionally mirror the legacy renderer's default
``show_releases`` and ``show_branches`` patterns without reading ``.render``.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from collections.abc import Iterable


DEFAULT_RELEASE_PATTERN = r"^v[0-9]+\.[0-9]+$|^v[0-9]+\.[0-9]+\.[0-9]+$"
DEFAULT_BRANCH_PATTERN = r"^v[0-9]+\.[0-9]+-dev$|^v[0-9]+\.[0-9]+\.x$|^publish-"


def matching_refs(
    lines: Iterable[str],
    release_pattern: str = DEFAULT_RELEASE_PATTERN,
    branch_pattern: str = DEFAULT_BRANCH_PATTERN,
) -> list[tuple[str, str]]:
    """Return unique ``(kind, name)`` pairs matching the configured rules."""
    release_re = re.compile(release_pattern) if release_pattern else None
    branch_re = re.compile(branch_pattern) if branch_pattern else None
    selected: set[tuple[str, str]] = set()

    for line in lines:
        fields = line.strip().split(None, 1)
        if len(fields) != 2:
            continue
        ref = fields[1]
        if ref.endswith("^{}"):
            continue
        if ref.startswith("refs/tags/"):
            kind, name, pattern = "tag", ref.removeprefix("refs/tags/"), release_re
        elif ref.startswith("refs/heads/"):
            kind, name, pattern = "branch", ref.removeprefix("refs/heads/"), branch_re
        else:
            continue
        if pattern is not None and pattern.search(name):
            selected.add((kind, name))

    return sorted(selected, key=lambda item: (item[0], item[1]))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--release-pattern",
        default=os.environ.get("RELEASE_PATTERN", DEFAULT_RELEASE_PATTERN),
    )
    parser.add_argument(
        "--branch-pattern",
        default=os.environ.get("BRANCH_PATTERN", DEFAULT_BRANCH_PATTERN),
    )
    args = parser.parse_args()

    for kind, name in matching_refs(
        sys.stdin,
        release_pattern=args.release_pattern,
        branch_pattern=args.branch_pattern,
    ):
        print(f"{kind}\t{name}")


if __name__ == "__main__":
    main()
