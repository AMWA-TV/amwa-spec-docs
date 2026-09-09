#!/usr/bin/env bash
#
# Prepare the docs/ tree for the Zensical site build.
#
# Documentation sources use repository-relative links so they remain useful
# when browsing the source on GitHub. Those paths do not exist in the
# published docs tree, so links that leave docs/ are rewritten to the source
# repository at the ref being published.

set -euo pipefail

REPO_SLUG="${GITHUB_REPOSITORY:?GITHUB_REPOSITORY must be set}"
REF="${BUILD_REF:-${GITHUB_REF_NAME:-main}}"
REPO_URL="https://github.com/${REPO_SLUG}/blob/${REF}"
PUBLIC_DOCS_ROOT="${PUBLIC_DOCS_ROOT:-https://specs.amwa.tv/${REPO_SLUG##*/}}"
TOOLKIT_DIR="${TOOLKIT_DIR:-.}"

# Zensical uses site_url for canonical links. Mike appends the published
# version, so this must remain the unversioned public root.
python3 - "${PUBLIC_DOCS_ROOT%/}/" <<'PY'
from pathlib import Path
import json
import os
import re
import sys

config = Path("zensical.toml")
readme = Path("README.md")
site_url = sys.argv[1]
metadata_dir_value = os.environ.get("METADATA_DIR")
metadata_readme = (
    Path(metadata_dir_value) / "README.md"
    if metadata_dir_value
    else Path(".amwa-metadata-unavailable")
)


def read_title(path):
    if not path.is_file():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^#\s+(.+?)\s*$", line)
        if match:
            return match.group(1)
    return None


metadata_title = read_title(metadata_readme)
site_name = metadata_title or read_title(readme) or os.environ.get(
    "SITE_NAME", "documentation"
)
repo_slug = os.environ.get("GITHUB_REPOSITORY", "documentation")
repo_url = f"https://github.com/{repo_slug}"

if not config.is_file():
    # Historical specification refs predate the shared Zensical migration.
    # Use current repository metadata for the site chrome while retaining the
    # historical documentation content below.
    config.write_text(
        "[project]\n"
        f"site_name = {json.dumps(site_name)}\n"
        f"site_url = {json.dumps(site_url)}\n"
        f"repo_name = {json.dumps(repo_slug)}\n"
        f"repo_url = {json.dumps(repo_url)}\n"
        'extra_css = ["stylesheets/extra.css"]\n'
        'extra_javascript = ["javascripts/json-viewer.js"]\n\n'
        "[project.markdown_extensions.pymdownx.tabbed]\n"
        "alternate_style = true\n\n"
        "[project.markdown_extensions.pymdownx.superfences]\n\n"
        "[project.markdown_extensions.toc]\n"
        "permalink = false\n\n"
        "[project.extra.version]\n"
        'provider = "mike"\n',
        encoding="utf-8",
    )
else:
    text = config.read_text(encoding="utf-8")
    updated = re.sub(
        r"(?m)^site_url\s*=.*$",
        f'site_url = "{site_url}"',
        text,
        count=1,
    )
    if updated != text:
        config.write_text(updated, encoding="utf-8")

# Keep the historical README body, but use the current metadata header so
# published versions have the same title, badges, and repository link.
if metadata_readme.is_file() and readme.is_file():
    marker = "<!-- INTRO-START -->"
    metadata_text = metadata_readme.read_text(encoding="utf-8")
    historical_text = readme.read_text(encoding="utf-8")
    if marker in metadata_text and marker in historical_text:
        metadata_header = metadata_text.split(marker, 1)[0].rstrip()
        historical_body = historical_text.split(marker, 1)[1]
        readme.write_text(
            f"{metadata_header}\n\n{marker}{historical_body}",
            encoding="utf-8",
        )
PY

# Stage the shared AMWA branding and add it to the Zensical header. The
# repository family determines whether the NMOS logo is included: IN repos use
# AMWA only; IS, BCP, and INFO repos use both logos.
python3 - <<'PY'
from pathlib import Path
import json
import os
import re
import shutil

repo_name = os.environ["GITHUB_REPOSITORY"].rsplit("/", 1)[-1]
toolkit_dir = Path(os.environ["TOOLKIT_DIR"])
asset_names = ["AMWA-logo.png"]
if repo_name.startswith(("is-", "bcp-", "info-")):
    asset_names.append("NMOS-logo.png")

for name in asset_names:
    source = toolkit_dir / "assets" / "images" / name
    if not source.is_file():
        raise SystemExit(f"branding asset not found: {source}")
    destination = Path("docs/images") / name
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)

css = """\
:root {
  --md-primary-fg-color: #418ab3;
  --md-primary-fg-color--light: #a5cadf;
  --md-primary-fg-color--dark: #418ab3;
  --md-primary-bg-color: #d1e4ef;
  --md-primary-bg-color--light: #d1e4ef;
}

/* Match the title and navigation colours used by specs.amwa.tv/nmos. */
.md-header {
  background-color: #418ab3;
  color: #d1e4ef;
}

.md-header a {
  color: #d1e4ef;
}

.md-tabs {
  background-color: #a5cadf;
}

.md-tabs__link {
  color: #418ab3;
}

.md-search__form {
  background-color: #a5cadf;
}

.md-search__input {
  color: #418ab3;
}

.md-search__input::placeholder {
  color: rgba(65, 138, 179, 0.75);
}

.md-nav__link--active {
  background-color: #a5cadf;
  color: #418ab3;
}

.amwa-header-branding {
  align-items: center;
  display: flex;
  flex: 0 0 auto;
  gap: 0.45rem;
  margin-inline: 0.5rem;
}

.amwa-header-branding a {
  align-items: center;
  display: flex;
}

.amwa-header-branding img {
  display: block;
  height: 1.55rem;
  object-fit: contain;
  width: auto;
}

.amwa-header-branding a + a {
  border-left: 1px solid rgba(209, 228, 239, 0.7);
  padding-left: 0.45rem;
}

@media screen and (max-width: 600px) {
  .amwa-header-branding img {
    height: 1.25rem;
  }
}
"""
Path("docs/stylesheets").mkdir(parents=True, exist_ok=True)
Path("docs/stylesheets/amwa-branding.css").write_text(css, encoding="utf-8")

logos = [
    {
        "file": name,
        "alt": name.removesuffix("-logo.png") + " logo",
        "href": (
            "https://www.amwa.tv"
            if name == "AMWA-logo.png"
            else "https://specs.amwa.tv/new/nmos"
        ),
    }
    for name in asset_names
]
js = f"""(() => {{
  const header = document.querySelector('.md-header__inner') || document.querySelector('header');
  if (!header || header.querySelector('.amwa-header-branding')) return;

  const scriptUrl = document.currentScript && document.currentScript.src;
  const assetUrl = (file) => new URL(`../images/${{file}}`, scriptUrl || window.location.href).href;
  const branding = document.createElement('div');
  branding.className = 'amwa-header-branding';
  branding.setAttribute('aria-label', 'AMWA branding');

  for (const logo of {json.dumps(logos)}) {{
    const link = document.createElement('a');
    link.href = logo.href;
    link.setAttribute('aria-label', logo.alt);
    const image = document.createElement('img');
    image.src = assetUrl(logo.file);
    image.alt = logo.alt;
    link.appendChild(image);
    branding.appendChild(link);
  }}

  header.insertBefore(branding, header.firstChild);
}})();
"""
Path("docs/javascripts").mkdir(parents=True, exist_ok=True)
Path("docs/javascripts/amwa-branding.js").write_text(js, encoding="utf-8")

config = Path("zensical.toml")
text = config.read_text(encoding="utf-8")
project = re.search(r"(?ms)^\[project\]\n.*?(?=^\[|\Z)", text)
if not project:
    raise SystemExit("[project] section not found in zensical.toml")
section = project.group(0)


def add_to_array(section_text, key, value):
    match = re.search(rf"(?ms)^{re.escape(key)}\s*=\s*\[(.*?)\]", section_text)
    if match:
        if value in match.group(1):
            return section_text
        existing = match.group(1).rstrip()
        if existing and not existing.endswith(","):
            existing += ","
        replacement = f'{key} = [{existing}\n    {json.dumps(value)},\n]'
        return section_text[:match.start()] + replacement + section_text[match.end():]
    return section_text.rstrip() + f'\n{key} = [{json.dumps(value)}]\n'

section = add_to_array(section, "extra_css", "stylesheets/amwa-branding.css")
section = add_to_array(section, "extra_javascript", "javascripts/amwa-branding.js")
config.write_text(text[:project.start()] + section + text[project.end():], encoding="utf-8")
PY

if [[ ! -f README.md ]]; then
    echo "error: README.md not found (run from repo root)" >&2
    exit 1
fi

# Zensical builds from docs/, while these optional source directories live at
# repository root. Stage them into the temporary docs tree for the site build.
for directory in APIs examples; do
    if [[ -d "${directory}" ]]; then
        rm -rf "docs/${directory}"
        cp -R "${directory}" "docs/${directory}"
    fi
done

# docs/README.md is a legacy Jekyll navigation source, not a documentation
# page. The generated index pages and Zensical's implicit navigation replace it.
rm -f docs/README.md

# Render discovered RAML, schema, and example assets and generate their index
# pages. This must happen after root-level assets have been staged into docs/.
python3 "${TOOLKIT_DIR}/scripts/render-doc-assets.py"

# Generate the documentation landing page from README.md. A docs/ directory
# link in README points to the documentation currently being viewed.
sed -E \
    -e 's#\]\(docs/\)#](Overview.md)#g' \
    -e 's#\]\(docs/([^)]+)\)#](\1)#g' \
    -e "s#\]\(\./?LICENSE(\.txt|\.md)?\)#](${REPO_URL}/LICENSE\1)#g" \
    -e "s#\]\(LICENSE(\.txt|\.md)?\)#](${REPO_URL}/LICENSE\1)#g" \
    -e "s#\]\(CONTRIBUTING\.md\)#](${REPO_URL}/CONTRIBUTING.md)#g" \
    -e "s#\]\(SECURITY\.md\)#](${REPO_URL}/SECURITY.md)#g" \
    -e "s#https://github.com/${REPO_SLUG}/blob/[0-9a-f]+/docs/([^)\" ]+)#\1#g" \
    README.md > docs/index.md

echo "Generated docs/index.md from README.md"

# Rewrite links from docs/*.md to repository files. Also remove Jekyll-only
# table-of-contents directives left in older documentation.
shopt -s nullglob
for file in docs/*.md; do
    [[ "${file}" == "docs/index.md" ]] && continue
    sed -i -E \
        -e 's#\]\(\.\./APIs/schemas/#](__DOCS_SCHEMA_ASSET__/#g' \
        -e 's#\]\(\.\./APIs/#](__DOCS_ASSET__/APIs/#g' \
        -e 's#\]\(\.\./examples/#](__DOCS_ASSET__/examples/#g' \
        -e "s#\]\(\.\./([^)]+)\)#](${REPO_URL}/\1)#g" \
        -e 's#\]\(__DOCS_SCHEMA_ASSET__/#](../schemas/#g' \
        -e 's#\]\(__DOCS_ASSET__/(APIs|examples)/#](../\1/#g' \
        -e "/^\{:\.no_toc\}/,/^[[:space:]]*\{:toc\}/d" \
        "${file}"
done

echo "Rewrote repository-relative links to ${REPO_URL}"
