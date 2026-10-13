#!/usr/bin/env python3
"""Generate static HTML compatibility pages for legacy documentation URLs.

The generated tree is intended to be overlaid at the legacy site's document
root. It contains no rewrite rules and no dependency on the old renderer. Each
page displays a short migration notice, provides a fallback link, and moves
the browser after a short delay while preserving the incoming query string and
fragment.
"""


import argparse
import csv
import html
import json
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit, urlunsplit

BRIDGE_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="robots" content="noindex">
  <title>AMWA specification link moved</title>
  <link rel="canonical" href="{target}">
  <meta http-equiv="refresh" content="5;url={target}">
  <style>
    body {{
      max-width: 44rem;
      margin: 4rem auto;
      padding: 0 1.25rem;
      color: #222;
      font: 16px/1.5 system-ui, sans-serif;
    }}
    h1 {{ font-size: 1.6rem; }}
    a {{ overflow-wrap: anywhere; }}
  </style>
</head>
<body>
  <h1>This specification page has moved</h1>
  <p>
    This legacy URL is retained temporarily. Please update your bookmark or
    documentation to the new link below.
  </p>
  <p><a id="destination" href="{target}">{target_display}</a></p>
  <p>You will be redirected automatically in a few seconds.</p>
  <script>
    (() => {{
      const target = {target_json};
      const destination = target + window.location.search + window.location.hash;
      const link = document.getElementById("destination");
      link.href = destination;
      window.setTimeout(() => window.location.replace(destination), 4000);
    }})();
  </script>
</body>
</html>
"""


def target_for(row: dict[str, str], target_prefix: str | None) -> str:
    target = row["target_url"]
    if not target_prefix:
        return target

    old = urlsplit(target)
    new = urlsplit(target_prefix)
    if old.netloc != new.netloc or old.scheme != new.scheme:
        raise ValueError(f"target and target prefix use different origins: {target}")

    canonical_root = new.path.rstrip("/")
    if not canonical_root:
        raise ValueError(f"target prefix has no canonical site path: {target_prefix}")

    # Accept both inventories created before the site migration (/new/<site>)
    # and current inventories that already contain the canonical /<site> path.
    # In either case, publish the bridge target below the canonical prefix.
    accepted_roots = (canonical_root, f"/new{canonical_root}")
    for root in accepted_roots:
        if old.path == root:
            suffix = ""
            break
        if old.path.startswith(root + "/"):
            suffix = old.path[len(root) + 1 :]
            break
    else:
        roots = " or ".join(f"{root}/" for root in accepted_roots)
        raise ValueError(f"target is outside the expected {roots} tree: {target}")

    new_path = canonical_root + (f"/{suffix}" if suffix else "/")
    return urlunsplit((new.scheme, new.netloc, new_path, old.query, old.fragment))


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


def render_bridge(target: str) -> str:
    escaped_target = html.escape(target, quote=True)
    return BRIDGE_HTML.format(
        target=escaped_target,
        target_display=html.escape(target),
        target_json=json.dumps(target),
    )


def generate(
    csv_path: Path,
    output_dir: Path,
    source_prefix: str,
    target_prefix: str | None,
    include_classes: set[str] | None,
) -> int:
    generated = 0
    collisions: dict[Path, str] = {}

    with csv_path.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))

    source_paths = {urlsplit(row["legacy_url"]).path for row in rows}
    for row in rows:
        if include_classes and row.get("mapping_class") not in include_classes:
            continue
        if row.get("legacy_content_type") != "text/html":
            continue
        target = row.get("target_url", "")
        if not target:
            continue

        # Apache normally turns a directory URL without a trailing slash
        # into the slash-terminated URL before serving its index.  A
        # static tree cannot contain both a file called v1.0.1 and a
        # directory called v1.0.1, so let that normal directory
        # canonicalization handle the former.
        source_path = urlsplit(row["legacy_url"]).path
        if not source_path.endswith("/") and source_path + "/" in source_paths:
            continue

        destination = relative_source_path(row["legacy_url"], source_prefix)
        previous = collisions.get(destination)
        if previous and previous != target:
            raise ValueError(
                f"multiple targets for {destination}: {previous} and {target}"
            )
        collisions[destination] = target

        target = target_for(row, target_prefix)
        output_path = output_dir / destination
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(render_bridge(target), encoding="utf-8")
        generated += 1

    return generated


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-prefix", default="/is-08/")
    parser.add_argument(
        "--target-prefix",
        help=(
            "replace a target under the supplied canonical prefix (or its "
            "legacy /new/<site>/ equivalent), for example "
            "https://specs.amwa.tv/is-08/"
        ),
    )
    parser.add_argument(
        "--mapping-class",
        action="append",
        dest="mapping_classes",
        help="restrict output to this mapping class (may be repeated)",
    )
    args = parser.parse_args()

    try:
        generated = generate(
            args.csv,
            args.output,
            args.source_prefix,
            args.target_prefix,
            set(args.mapping_classes) if args.mapping_classes else None,
        )
    except (OSError, ValueError, KeyError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(f"generated {generated} HTML bridge pages in {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
