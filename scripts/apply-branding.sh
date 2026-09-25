#!/usr/bin/env bash
#
# Add shared AMWA branding to a prepared Zensical documentation tree.
#
# This is separate from prepare-docs.sh so repositories with custom source
# generation can retain their own preparation step while using the shared
# header branding.

set -euo pipefail

: "${GITHUB_REPOSITORY:?GITHUB_REPOSITORY must be set}"
: "${TOOLKIT_DIR:?TOOLKIT_DIR must be set}"

python3 - <<'PY'
from pathlib import Path
import json
import os
import re
import shutil

repo_name = os.environ["GITHUB_REPOSITORY"].rsplit("/", 1)[-1]
toolkit_dir = Path(os.environ["TOOLKIT_DIR"])
docs_dir = Path(os.environ.get("DOCS_DIR", "docs"))
asset_names = ["AMWA-logo.png"]
logo_specs = [
    {
        "file": "AMWA-logo.png",
        "alt": "AMWA logo",
        "href": "https://www.amwa.tv",
    }
]
if repo_name.startswith("in-"):
    logo_specs.append(
        {
            "src": "https://static.wixstatic.com/media/219a48_9e03812d08064ed0a8be326563d9cb9c~mv2.png",
            "alt": "JT-DMF logo",
            "href": "https://specs.amwa.tv/in-index",
        }
    )
elif (
    repo_name == "nmos"
    or repo_name in {"nmos-parameter-registers", "nmos-control-feature-sets"}
    or repo_name.startswith(("is-", "ms-", "bcp-", "info-"))
):
    asset_names.append("NMOS-logo.png")
    logo_specs.append(
        {
            "file": "NMOS-logo.png",
            "alt": "NMOS logo",
            "href": "https://specs.amwa.tv/new/nmos",
        }
    )

for name in asset_names:
    source = toolkit_dir / "assets" / "images" / name
    if not source.is_file():
        raise SystemExit(f"branding asset not found: {source}")
    destination = docs_dir / "images" / name
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

.md-search__form:hover,
.md-search__form:focus-within {
  background-color: #d1e4ef;
}

.md-search__input {
  color: #418ab3;
}

.md-search__input::placeholder {
  color: rgba(65, 138, 179, 0.75);
}

.md-sidebar .md-nav__link:hover {
  background-color: #a5cadf;
  color: #418ab3;
}

/* Highlight only the exact current page, not its active ancestor sections. */
.md-sidebar--primary .amwa-current-page {
  background-color: #a5cadf !important;
  color: #418ab3 !important;
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

.amwa-header-branding a + a,
.amwa-header-branding a + img {
  border-left: 1px solid rgba(209, 228, 239, 0.7);
  padding-left: 0.45rem;
}

@media screen and (max-width: 600px) {
  .amwa-header-branding img {
    height: 1.25rem;
  }
}
"""
(docs_dir / "stylesheets").mkdir(parents=True, exist_ok=True)
(docs_dir / "stylesheets" / "amwa-branding.css").write_text(css, encoding="utf-8")

js = f"""(() => {{
  const header = document.querySelector('.md-header__inner') || document.querySelector('header');
  if (!header || header.querySelector('.amwa-header-branding')) return;

  const scriptUrl = document.currentScript && document.currentScript.src;
  const assetUrl = (file) => new URL(`../images/${{file}}`, scriptUrl || window.location.href).href;
  const branding = document.createElement('div');
  branding.className = 'amwa-header-branding';
  branding.setAttribute('aria-label', 'AMWA branding');

  for (const logo of {json.dumps(logo_specs)}) {{
    const image = document.createElement('img');
    image.src = logo.src || assetUrl(logo.file);
    image.alt = logo.alt;
    if (logo.href) {{
      const link = document.createElement('a');
      link.href = logo.href;
      link.setAttribute('aria-label', logo.alt);
      link.appendChild(image);
      branding.appendChild(link);
    }} else {{
      branding.appendChild(image);
    }}
  }}

  header.insertBefore(branding, header.firstChild);

  const normalisePath = (path) => {{
    const trimmed = path.replace(/index\\.html$/, '').replace(/\\/+$/, '');
    return `${{trimmed}}/`;
  }};
  const currentPath = normalisePath(window.location.pathname);
  document.querySelectorAll('.md-sidebar--primary a.md-nav__link').forEach((link) => {{
    const target = new URL(link.href, window.location.href);
    if (target.origin === window.location.origin && normalisePath(target.pathname) === currentPath) {{
      link.classList.add('amwa-current-page');
    }}
  }});
}})();
"""
(docs_dir / "javascripts").mkdir(parents=True, exist_ok=True)
(docs_dir / "javascripts" / "amwa-branding.js").write_text(js, encoding="utf-8")

config = Path("zensical.toml")
if config.is_file():
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
else:
    config = Path("mkdocs.yml")
    if not config.is_file():
        raise SystemExit("neither zensical.toml nor mkdocs.yml was found")
    text = config.read_text(encoding="utf-8")

    def add_yaml_list(section_text, key, value):
        if re.search(rf"(?m)^\s*-\s*{re.escape(value)}\s*$", section_text):
            return section_text
        match = re.search(
            rf"(?m)^{re.escape(key)}:[ \t]*\n(?P<items>(?:[ \t]+-[^\n]*\n)*)",
            section_text,
        )
        if match:
            return section_text[:match.end()] + f"  - {value}\n" + section_text[match.end():]
        return section_text.rstrip() + f"\n{key}:\n  - {value}\n"

    text = add_yaml_list(text, "extra_css", "stylesheets/amwa-branding.css")
    text = add_yaml_list(text, "extra_javascript", "javascripts/amwa-branding.js")
    config.write_text(text, encoding="utf-8")
PY
