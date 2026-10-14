#!/usr/bin/env python3
"""Copy mapped non-HTML assets into the legacy compatibility tree.

The HTML bridge generator creates redirect pages, but raw JSON, SDP, and other
assets must remain actual files at their historical paths. This script copies
each mapped non-HTML target from the freshly exported site into the relative
legacy path before the compatibility tree is uploaded.
"""

import argparse
import csv
import shutil
from pathlib import Path
from urllib.parse import unquote, urlsplit


def target_for(row: dict[str, str], target_prefix: str) -> str:
    target = row["target_url"]
    old = urlsplit(target)
    new = urlsplit(target_prefix)
    if old.scheme != new.scheme or old.netloc != new.netloc:
        raise ValueError(f"target and target prefix use different origins: {target}")

    canonical_root = new.path.rstrip("/")
    if old.path == canonical_root:
        suffix = ""
    elif old.path.startswith(canonical_root + "/"):
        suffix = old.path[len(canonical_root) + 1 :]
    else:
        raise ValueError(f"target is outside the expected {canonical_root}/ tree: {target}")

    return unquote(suffix)


def relative_source_path(source_url: str, source_prefix: str) -> Path:
    parsed = urlsplit(source_url)
    root = source_prefix.rstrip("/")
    prefix = root + "/"
    if parsed.netloc != "specs.amwa.tv":
        raise ValueError(f"source is outside specs.amwa.tv: {source_url}")
    if parsed.path == root:
        relative = ""
    elif parsed.path.startswith(prefix):
        relative = parsed.path[len(prefix) :]
    else:
        raise ValueError(f"source is outside {prefix}: {source_url}")

    relative = unquote(relative)
    if not relative or relative.endswith("/"):
        relative = relative + "index.html"

    path = Path(relative)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"unsafe source path: {source_url}")
    return path


def copy_assets(
    csv_path: Path,
    site_dir: Path,
    source_prefix: str,
    target_prefix: str,
) -> int:
    copied = 0
    destinations: dict[Path, str] = {}

    with csv_path.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))

    for row in rows:
        if row.get("legacy_content_type") == "text/html":
            continue
        target = row.get("target_url", "")
        if not target:
            continue

        destination = relative_source_path(row["legacy_url"], source_prefix)
        previous = destinations.get(destination)
        if previous and previous != target:
            raise ValueError(
                f"multiple targets for {destination}: {previous} and {target}"
            )
        destinations[destination] = target

        target_relative = target_for(row, target_prefix)
        if not target_relative:
            raise ValueError(f"non-HTML target has no file path: {target}")
        source = site_dir / target_relative
        if not source.is_file():
            raise FileNotFoundError(
                f"mapped target is not present in exported site: {source} ({target})"
            )

        output = site_dir / destination
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, output)
        copied += 1

    return copied


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, required=True)
    parser.add_argument("--site", type=Path, required=True)
    parser.add_argument("--source-prefix", required=True)
    parser.add_argument("--target-prefix", required=True)
    args = parser.parse_args()

    try:
        copied = copy_assets(
            args.csv,
            args.site,
            args.source_prefix,
            args.target_prefix,
        )
    except (OSError, ValueError, KeyError) as exc:
        parser.error(str(exc))

    print(f"copied {copied} legacy non-HTML assets into {args.site}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
