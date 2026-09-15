#!/usr/bin/env python3
"""Create a compact searchable manifest from a built Zensical site.

The manifest is intentionally static so an index site can merge manifests from
many AMWA repositories without crawling or executing the documentation sites.
It is written beside the generated site and is published at the repository's
unversioned documentation root by the shared workflow.
"""

from __future__ import annotations

import json
import os
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote


SITE = Path(os.environ.get("SITE_DIR", "site"))
PUBLIC_ROOT = os.environ.get("PUBLIC_DOCS_ROOT", "").rstrip("/")
REPOSITORY = os.environ.get("GITHUB_REPOSITORY", "")


class PageParser(HTMLParser):
    """Extract readable page text while ignoring site chrome and scripts."""

    _ignored = {"footer", "header", "nav", "script", "style", "svg", "noscript"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.ignored_depth = 0
        self.title: list[str] = []
        self.headings: list[str] = []
        self.body: list[str] = []
        self._active_heading: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self._ignored:
            self.ignored_depth += 1
        if self.ignored_depth:
            return
        if tag == "title":
            self._active_heading = self.title
        elif tag in {"h1", "h2", "h3"}:
            self._active_heading = []

    def handle_endtag(self, tag: str) -> None:
        if tag in {"title", "h1", "h2", "h3"}:
            if tag != "title" and self._active_heading:
                self.headings.append(" ".join(self._active_heading))
            self._active_heading = None
        if tag in self._ignored and self.ignored_depth:
            self.ignored_depth -= 1

    def handle_data(self, data: str) -> None:
        if self.ignored_depth or not data.strip():
            return
        value = re.sub(r"\s+", " ", data).strip()
        if self._active_heading is not None:
            self._active_heading.append(value)
        self.body.append(value)


def normalise(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def page_url(path: Path) -> str:
    relative = path.relative_to(SITE).as_posix()
    if relative == "index.html":
        suffix = ""
    elif relative.endswith("/index.html"):
        suffix = relative[: -len("index.html")]
    else:
        suffix = relative[: -len(".html")] + "/"
    encoded = quote(suffix, safe="/@:._~-")
    root = PUBLIC_ROOT or "/"
    return f"{root}/latest/{encoded}".replace("//latest", "/latest")


def render_page(path: Path) -> dict[str, str] | None:
    parser = PageParser()
    parser.feed(path.read_text(encoding="utf-8", errors="replace"))
    title = normalise(" ".join(parser.headings[:1]) or " ".join(parser.title))
    if not title:
        title = path.stem.replace("_", " ")
    text = normalise(" ".join(parser.body))
    if not text:
        return None
    return {
        "title": title,
        "url": page_url(path),
        "text": normalise(f"{title} {' '.join(parser.headings)} {text}")[:6000],
        "repository": REPOSITORY,
    }


def main() -> None:
    documents = []
    for path in sorted(SITE.rglob("*.html")):
        if path.is_file() and path.name != "404.html":
            document = render_page(path)
            if document:
                documents.append(document)

    output = {
        "version": 1,
        "repository": REPOSITORY,
        "documents": documents,
    }
    destination = SITE / "global-search.json"
    destination.write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Wrote {destination} with {len(documents)} documents")


if __name__ == "__main__":
    main()
