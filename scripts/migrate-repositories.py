#!/usr/bin/env python3
"""Migrate a list of AMWA documentation repositories to canonical URLs.

The command intentionally does not commit, push, dispatch workflows, or touch
``.github/workflows/render.yml``. It crawls the existing legacy site, creates a
legacy URL mapping, updates the shared Zensical caller workflow, and removes
the obsolete Legacy Render badge from README.md.

Use ``--apply`` to write changes. Without it, the command performs the crawl,
mapping, and target checks but leaves repositories unchanged. Both versioned
and fixed-``latest`` repositories that call the shared workflow are supported.
"""

from __future__ import annotations

import argparse
import csv
import re
import subprocess
import sys
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, unquote, urljoin, urlsplit, urlunsplit
from urllib.request import Request, urlopen

CANONICAL_HOST = "specs.amwa.tv"
MAPPING_FIELDS = [
    "legacy_url",
    "legacy_status",
    "target_url",
    "target_status_current",
    "mapping_class",
    "legacy_content_type",
    "legacy_location",
    "target_content_type",
    "target_effective_url",
]


class LinkParser(HTMLParser):
    """Collect URL-bearing attributes from a legacy HTML document."""

    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del tag
        for name, value in attrs:
            if name.lower() in {"href", "src", "data-src", "data"} and value:
                self.links.append(value)


def content_type_for(path: str, content_type: str) -> str:
    if content_type:
        return content_type.split(";", 1)[0].strip().lower()

    lower = path.lower()
    if lower.endswith((".html", ".htm", "/")):
        return "text/html"
    if "." not in lower.rsplit("/", 1)[-1]:
        return "text/html"
    if lower.endswith(".json"):
        return "application/json"
    if lower.endswith(".png"):
        return "image/png"
    if lower.endswith(".js"):
        return "application/javascript"
    if lower.endswith(".css"):
        return "text/css"
    return "application/octet-stream"


def site_root(site_name: str) -> str:
    return f"https://{CANONICAL_HOST}/{site_name}"


def normalise_url(raw: str, site_name: str) -> str | None:
    """Return a normalized URL if *raw* remains inside this specification."""

    if not raw:
        return None

    root = site_root(site_name)
    joined = urljoin(root + "/", raw.strip())
    parsed = urlsplit(joined)
    root_path = "/" + site_name
    if parsed.scheme not in {"http", "https"} or parsed.netloc != CANONICAL_HOST:
        return None
    if parsed.path != root_path and not parsed.path.startswith(root_path + "/"):
        return None

    path = quote(unquote(parsed.path), safe="/%:@-._~!$&'()*+,;=%")
    return urlunsplit(("https", CANONICAL_HOST, path, parsed.query, ""))


def fetch_document(url: str, timeout: float) -> tuple[int, str, str, bytes]:
    """Fetch a URL, preserving useful metadata for HTTP errors as well."""

    request = Request(url, headers={"User-Agent": "AMWA-doc-migration/1.0"})
    try:
        with urlopen(request, timeout=timeout) as response:
            content_type = content_type_for(
                urlsplit(url).path, response.headers.get("Content-Type", "")
            )
            return response.status, content_type, response.geturl(), response.read(2_000_000)
    except HTTPError as error:
        content_type = content_type_for(
            urlsplit(url).path, error.headers.get("Content-Type", "")
        )
        try:
            body = error.read(2_000_000)
        except OSError:
            body = b""
        return error.code, content_type, error.geturl() or url, body
    except (OSError, URLError):
        return 0, content_type_for(urlsplit(url).path, ""), url, b""


def crawl_legacy_site(
    site_name: str,
    *,
    workers: int = 16,
    timeout: float = 30,
    max_urls: int = 20_000,
) -> list[dict[str, str]]:
    """Crawl legacy HTML links and return an inventory suitable for CSV output."""

    seeds = {site_root(site_name), site_root(site_name) + "/"}
    pending = set(seeds)
    seen: set[str] = set()
    results: dict[str, dict[str, str]] = {}

    def fetch_one(url: str) -> tuple[str, int, str, str, list[str]]:
        status, content_type, final_url, body = fetch_document(url, timeout)
        links: list[str] = []
        if content_type == "text/html" and body:
            parser = LinkParser()
            parser.feed(body.decode("utf-8", "replace"))
            links = [
                normalized
                for raw_link in parser.links
                if (normalized := normalise_url(raw_link, site_name))
            ]
        return url, status, content_type, final_url, links

    with ThreadPoolExecutor(max_workers=workers) as pool:
        while pending and len(seen) < max_urls:
            batch = list(pending)[: min(workers * 4, max_urls - len(seen))]
            pending.difference_update(batch)
            batch = [url for url in batch if url not in seen]
            seen.update(batch)

            for url, status, content_type, final_url, links in pool.map(fetch_one, batch):
                results[url] = {
                    "legacy_url": url,
                    "legacy_status": str(status),
                    "legacy_content_type": content_type,
                    "legacy_location": final_url if final_url != url else "",
                }
                pending.update(link for link in links if link not in seen)

    if pending and len(seen) >= max_urls:
        raise RuntimeError(
            f"legacy crawl for {site_name} reached --max-urls={max_urls}; "
            "increase the limit if the site is intentionally larger"
        )

    return [results[url] for url in sorted(results)]


def git_ref(repo: Path, version: str) -> str | None:
    for ref in (version, f"origin/{version}"):
        result = subprocess.run(
            ["git", "rev-parse", "--verify", ref],
            cwd=repo,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        if result.returncode == 0:
            return ref
    return None


def documentation_stems(repo: Path, version: str) -> list[str]:
    ref = git_ref(repo, version)
    if not ref:
        return []
    result = subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", ref, "docs"],
        cwd=repo,
        text=True,
        capture_output=True,
        check=True,
    )
    return [
        Path(path).stem
        for path in result.stdout.splitlines()
        if path.endswith(".md") and Path(path).stem != "README"
    ]


def discover_default_version(site_name: str, timeout: float) -> str | None:
    status, content_type, _, body = fetch_document(site_root(site_name) + "/", timeout)
    if status and content_type == "text/html":
        match = re.search(r"Docs for\s+(v[0-9A-Za-z.-]+)", body.decode("utf-8", "replace"))
        if match:
            return match.group(1)
    return None


def encoded_doc_name(legacy_name: str, stems: Iterable[str]) -> str | None:
    stem = unquote(legacy_name)
    stem = re.sub(r"\.html?$", "", stem, flags=re.IGNORECASE).replace("_", " ")
    variants = [stem]
    numeric_prefix = re.match(r"^\d+\.\d+\.?\s*", stem)
    if numeric_prefix:
        variants.append(stem[numeric_prefix.end() :])

    available = list(stems)
    for variant in variants:
        if variant in available:
            return quote(variant, safe="-._~")
    for variant in variants:
        matches = [candidate for candidate in available if candidate.endswith(" - " + variant)]
        if len(matches) == 1:
            return quote(matches[0], safe="-._~")
    return None


def version_and_suffix(
    relative_path: str, default_version: str
) -> tuple[str, str]:
    match = re.match(r"^(?:releases|branches)/(v[^/]+)(?:/(.*))?$", relative_path)
    if match:
        return match.group(1), match.group(2) or ""
    return default_version, relative_path


def map_legacy_path(
    site_name: str,
    legacy_url: str,
    *,
    default_version: str,
    docs_by_version: dict[str, list[str]],
    versioned: bool = True,
) -> str:
    """Map one legacy path to a canonical suffix, or return an empty suffix."""

    root = "/" + site_name
    path = unquote(urlsplit(legacy_url).path)
    if path == root or path == root + "/":
        return "/"

    relative = path[len(root) :].lstrip("/")
    if relative in {"releases", "releases/", "branches", "branches/"}:
        return ""

    version, suffix = version_and_suffix(relative.rstrip("/"), default_version)
    if versioned and not version:
        return ""
    base = f"/{version}/" if versioned else "/"

    if re.fullmatch(r"v[^/]+", relative.rstrip("/")):
        return f"/{relative.rstrip('/')}/" if versioned else ""
    if suffix in {"", "docs"}:
        return base

    if suffix.startswith("codemirror/") or suffix == "json-formatter.js":
        return ""
    if suffix.startswith("docs/images/"):
        return f"{base}images/{suffix[len('docs/images/'):]}"
    if suffix.startswith("images/"):
        return f"{base}{suffix}"

    if suffix.startswith("APIs/schemas"):
        rest = suffix[len("APIs/schemas") :].strip("/")
        if not rest:
            return f"{base}schemas/"
        if rest.startswith(("resolved/", "with-refs/")):
            rest = rest.split("/", 1)[1] if "/" in rest else ""
            if not rest:
                return f"{base}schemas/"
        if rest.endswith(".html"):
            return f"{base}schemas/{rest[:-5]}/"
        if rest.endswith(".json"):
            return f"{base}schemas/{rest}"
        return ""

    if suffix.startswith("APIs/"):
        rest = suffix[len("APIs/") :].strip("/")
        if not rest:
            return f"{base}APIs/"
        if rest.endswith(".html"):
            return f"{base}APIs/{rest[:-5]}/"
        return ""

    if suffix.startswith("examples"):
        rest = suffix[len("examples") :].strip("/")
        if not rest:
            return f"{base}examples/"
        if rest.endswith(".html"):
            return f"{base}examples/{rest[:-5]}/"
        if rest.endswith(".json"):
            return f"{base}examples/{rest}"
        return ""

    if suffix.endswith(".json"):
        return f"{base}examples/{suffix}"

    if suffix.startswith("docs/"):
        suffix = suffix.removeprefix("docs/")

    if suffix.endswith(".html"):
        stem = encoded_doc_name(suffix, docs_by_version.get(version, []))
        if stem is None and version != default_version:
            stem = encoded_doc_name(suffix, docs_by_version.get(default_version, []))
        return f"{base}{stem}/" if stem else ""

    return ""


def staging_url(target_url: str, site_name: str, staging_prefix: str) -> str:
    canonical = site_root(site_name)
    staging = f"https://{CANONICAL_HOST}/{staging_prefix.strip('/')}/{site_name}"
    if target_url == canonical:
        return staging + "/"
    if target_url.startswith(canonical + "/"):
        return staging + target_url[len(canonical) :]
    raise ValueError(f"target is outside the expected {canonical}/ tree: {target_url}")


def verify_target(target_url: str, site_name: str, staging_prefix: str, timeout: float) -> tuple[str, str, str]:
    staging = staging_url(target_url, site_name, staging_prefix)
    status, content_type, effective, _ = fetch_document(staging, timeout)
    canonical = f"https://{CANONICAL_HOST}/{site_name}"
    if effective.startswith(f"https://{CANONICAL_HOST}/{staging_prefix.strip('/')}/{site_name}"):
        effective = canonical + effective[len(f"https://{CANONICAL_HOST}/{staging_prefix.strip('/')}/{site_name}") :]
    return str(status), content_type, effective


def workflow_is_versioned(text: str) -> bool:
    match = re.search(r"^\s*versioned:\s*(true|false)\s*$", text, re.MULTILINE | re.IGNORECASE)
    return not match or match.group(1).lower() == "true"


def build_mapping(
    repo: Path,
    site_name: str,
    inventory: list[dict[str, str]],
    *,
    timeout: float,
    verify: bool,
    staging_prefix: str,
    versioned: bool = True,
) -> list[dict[str, str]]:
    versions: list[str] = []
    for row in inventory:
        path = unquote(urlsplit(row["legacy_url"]).path)
        match = re.search(r"/(?:releases|branches)/(v[^/]+)", path)
        if match and match.group(1) not in versions:
            versions.append(match.group(1))

    if versioned:
        default_version = discover_default_version(site_name, timeout)
        if not default_version:
            default_version = versions[0] if versions else ""
        if default_version and default_version not in versions:
            versions.append(default_version)
        docs_by_version = {version: documentation_stems(repo, version) for version in versions}
    else:
        default_version = ""
        docs_by_version = {"": documentation_stems(repo, "HEAD")}

    rows: list[dict[str, str]] = []
    canonical = site_root(site_name)

    for source in inventory:
        suffix = map_legacy_path(
            site_name,
            source["legacy_url"],
            default_version=default_version,
            docs_by_version=docs_by_version,
            versioned=versioned,
        )
        target = canonical + suffix if suffix else ""
        row = {
            **source,
            "target_url": target,
            "target_status_current": "",
            "mapping_class": "no-target-rule" if not target else "confirmed-inventory",
            "target_content_type": "",
            "target_effective_url": "",
        }
        if target and verify:
            status, content_type, effective = verify_target(
                target, site_name, staging_prefix, timeout
            )
            row["target_status_current"] = status
            row["target_content_type"] = content_type
            row["target_effective_url"] = effective
            if status != "200":
                row["mapping_class"] = "expected-tree-not-currently-published"
        rows.append(row)

    return rows


def update_workflow_text(text: str, site_name: str) -> str:
    if "uses: AMWA-TV/amwa-spec-docs/.github/workflows/docs.yml@" not in text:
        raise ValueError("docs.yml does not call the shared AMWA documentation workflow")

    text = re.sub(
        r"^# Experimental shared-toolkit rendering\. The existing render\.yml workflow and\n"
        r"# \.render pipeline remain active until the new output has been accepted\.\n",
        "",
        text,
        flags=re.MULTILINE,
    )
    text = re.sub(
        r"^(\s*)public-docs-root:.*$",
        rf"\1public-docs-root: https://{CANONICAL_HOST}/{site_name}",
        text,
        count=1,
        flags=re.MULTILINE,
    )
    public_match = re.search(r"^(\s*)public-docs-root:.*$", text, re.MULTILINE)
    if not public_match:
        raise ValueError("docs.yml has no public-docs-root input")
    indent = public_match.group(1)

    def replace_or_insert(name: str, value: str, source: str) -> str:
        pattern = rf"^\s*{re.escape(name)}:.*$"
        replacement = f"{indent}{name}: {value}"
        if re.search(pattern, source, re.MULTILINE):
            return re.sub(pattern, replacement, source, count=1, flags=re.MULTILINE)
        marker = public_match.group(0)
        return source.replace(marker, marker + "\n" + replacement, 1)

    text = replace_or_insert("upload-prefix", "''", text)
    text = replace_or_insert("legacy-mapping", ".docs/legacy-mappings.csv", text)
    return text


def update_readme_text(text: str) -> str:
    return re.sub(r"^\[!\[Legacy Render Status\].*\n", "", text, flags=re.MULTILINE)


def write_mapping(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=MAPPING_FIELDS)
        writer.writeheader()
        writer.writerows({field: row.get(field, "") for field in MAPPING_FIELDS} for row in rows)


def resolve_repository(workspace: Path, value: str) -> Path:
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = workspace / candidate
    candidate = candidate.resolve()
    if not (candidate / ".git").exists():
        raise ValueError(f"not a Git repository: {candidate}")
    return candidate


def repository_is_dirty(repo: Path) -> bool:
    result = subprocess.run(
        ["git", "--no-optional-locks", "status", "--short"],
        cwd=repo,
        text=True,
        capture_output=True,
        check=True,
    )
    return bool(result.stdout.strip())


def migrate_repository(
    repo: Path,
    *,
    apply: bool,
    allow_dirty: bool,
    workers: int,
    timeout: float,
    max_urls: int,
    verify: bool,
    staging_prefix: str,
) -> tuple[int, int, int]:
    site_name = repo.name
    workflow = repo / ".github/workflows/docs.yml"
    readme = repo / "README.md"
    if not workflow.is_file():
        raise ValueError("missing .github/workflows/docs.yml")
    workflow_text = workflow.read_text(encoding="utf-8")
    updated_workflow = update_workflow_text(workflow_text, site_name)
    versioned = workflow_is_versioned(workflow_text)
    if apply and repository_is_dirty(repo) and not allow_dirty:
        raise ValueError("worktree is dirty; use --allow-dirty only after reviewing existing changes")

    inventory = crawl_legacy_site(
        site_name,
        workers=workers,
        timeout=timeout,
        max_urls=max_urls,
    )
    rows = build_mapping(
        repo,
        site_name,
        inventory,
        timeout=timeout,
        verify=verify,
        staging_prefix=staging_prefix,
        versioned=versioned,
    )

    mapped = sum(bool(row["target_url"]) for row in rows)
    no_target = len(rows) - mapped
    print(f"{site_name}: {len(rows)} legacy URLs, {mapped} mapped, {no_target} no-target rules")

    if apply:
        workflow.write_text(updated_workflow, encoding="utf-8")
        if readme.is_file():
            readme.write_text(update_readme_text(readme.read_text(encoding="utf-8")), encoding="utf-8")
        write_mapping(repo / ".docs/legacy-mappings.csv", rows)
        print(f"{site_name}: wrote workflow, README badge update, and .docs/legacy-mappings.csv")
    return len(rows), mapped, no_target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repos", nargs="+", help="repository names or paths to migrate")
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--apply", action="store_true", help="write changes; default is a dry run")
    parser.add_argument("--allow-dirty", action="store_true", help="allow applying to dirty worktrees")
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--timeout", type=float, default=30)
    parser.add_argument("--max-urls", type=int, default=20_000)
    parser.add_argument("--staging-prefix", default="new", help="current staging path prefix used for target checks")
    parser.add_argument("--no-verify-targets", action="store_true")
    args = parser.parse_args(argv)

    if args.workers < 1 or args.max_urls < 1:
        parser.error("--workers and --max-urls must be positive")

    try:
        repositories = [resolve_repository(args.workspace.resolve(), value) for value in args.repos]
        for repo in repositories:
            migrate_repository(
                repo,
                apply=args.apply,
                allow_dirty=args.allow_dirty,
                workers=args.workers,
                timeout=args.timeout,
                max_urls=args.max_urls,
                verify=not args.no_verify_targets,
                staging_prefix=args.staging_prefix,
            )
    except (OSError, RuntimeError, ValueError, subprocess.CalledProcessError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    if not args.apply:
        print("dry run only; use --apply after reviewing the inventories and targets")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
