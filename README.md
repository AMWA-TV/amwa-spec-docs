# AMWA documentation toolkit

Shared build scripts and a reusable GitHub Actions workflow for AMWA
specification repositories, including `is-*`, `ms-*`, `bcp-*`, `info-*`, and `in-*`
repositories.

The workflow builds a repository's Zensical site, stores versions with Mike on
its `gh-pages` branch, and uploads the complete site to the AMWA documentation
server at:

```text
/var/www/specs.amwa.tv/new/<site-name>
```

The server-facing root is a static redirect to `latest/`, so this does not
require `.htaccess` or directory-specific Apache configuration. Repositories
that contain `spec.yml` also publish the same metadata as `spec.json` at the
unversioned site root, for example `https://specs.amwa.tv/in-template/spec.json`.
This makes repository metadata available without a source checkout.

## Use from a documentation repository

A versioned repository can use a very small caller workflow:

```yaml
name: Documentation
run-name: ${{ case(github.event_name == 'push', '', github.event_name == 'release', format('Release - {0}', github.event.release.tag_name), format('Documentation - {0}', inputs.ref || github.ref_name)) }}

on:
  push:
    branches:
      - 'v[0-9]+.[0-9]+-dev'
      - 'v[0-9]+.[0-9]+.x'
      - 'publish-*'
  release:
  workflow_dispatch:
    inputs:
      ref:
        description: Optional branch or tag to rebuild
        required: false
        default: ''


permissions:
  contents: write

concurrency:
  group: amwa-documentation-${{ github.repository }}
  cancel-in-progress: false

jobs:
  docs:
    uses: AMWA-TV/amwa-spec-docs/.github/workflows/docs.yml@main
    with:
      versioned: true
      site-name: is-template
      public-docs-root: https://specs.amwa.tv/new/is-template
      source-ref: ${{ inputs.ref || github.ref_name }}
      # Use a released tag or commit SHA once the toolkit is released.
      toolkit-ref: main
    secrets: inherit
```

Push runs use GitHub's default commit title; GitHub shows the triggering
branch separately in the run metadata. Release runs are named `Release - <tag>`,
and manual runs are named `Documentation - <ref>`.

For an occasional full reconstruction of a versioned site's Mike tree, manually
dispatch the caller workflow with `rebuild_all: true`. This enumerates the
configured release and branch patterns and rebuilds each matching ref into
`gh-pages`; ordinary pushes and releases remain incremental.

For a single-version repository, use the same workflow with `versioned:
false`:

```yaml
jobs:
  docs:
    uses: AMWA-TV/amwa-spec-docs/.github/workflows/docs.yml@main
    with:
      versioned: false
      site-name: in-template
      public-docs-root: https://specs.amwa.tv/new/in-template
    secrets: inherit
```

Single-version repositories publish only `latest/` on `gh-pages`; they do not
create a duplicate version directory. Versioned repositories publish the
version represented by the triggering branch, release, or manually selected ref.
After every versioned deployment, `latest` is aliased to the highest stable
numeric GitHub release (for example `v1.2.0`). If there are no such releases,
`latest` is aliased to the highest-numbered `v<major>.<minor>-dev` or
`v<major>.<minor>.x` branch. If the selected release or branch has not yet
been published to Mike's `gh-pages` tree, the workflow builds that ref first;
this supports migrating repositories that already have historical releases.

### Inputs

| Input | Required | Default | Purpose |
| --- | --- | --- | --- |
| `site-name` | no | caller repository name | Directory below `/new/` and upload name |
| `public-docs-root` | yes | — | Unversioned public root used for canonical URLs |
| `versioned` | no | `true` | Select versioned or fixed-`latest` Mike behavior |
| `source-ref` | no | triggering ref | Build a selected branch/tag, useful for manual rebuilds |
| `toolkit-ref` | no | `main` | Shared toolkit ref; pin a release tag or SHA for production |
| `rebuild-all` | no | `false` | Manual recovery/migration mode: rebuild all matching refs into Mike's `gh-pages` tree |
| `release-pattern` | no | SemVer tags | Regex used by `rebuild-all` to select release tags |
| `branch-pattern` | no | Version branches and `publish-*` | Regex used by `rebuild-all` to select branches |

The caller repository must give the reusable workflow `contents: write`, and
must provide or inherit these secrets:

- `SSH_USER`
- `SSH_HOST`
- `SSH_PRIVATE_KEY`
- `SSH_KNOWN_HOSTS`

`GITHUB_TOKEN` is used by Mike to push the `gh-pages` branch.

## Repository requirements

The caller repository should contain:

- `README.md`
- `docs/`
- `zensical.toml`, with `provider = "mike"` under `project.extra.version`
- optional root-level `APIs/`, `examples/`, and `manifest/` directories

For historical refs that predate the Zensical migration, the workflow fetches
metadata from the repository's current default branch. `prepare-docs.sh` then
generates a minimal `zensical.toml` in the historical build checkout and uses
the current metadata header (title, badges, and repository link) with the
historical README body. `prepare-docs.sh` runs from the caller repository root. It stages optional
assets, discovers RAML/JSON files, optionally generates foldable source pages when
source-viewer assets are present, rewrites source links,
and sets `site_url` to `public-docs-root`. Mike then appends the version. Do not
set `site_url` to a versioned path in the source configuration.

The generated JSON pages use the same foldable source viewer as the YAML
source pages, with `Folding`/`Raw` views, line numbers, nested folding,
and `Expand all`/`Collapse all` controls. The generated pages do not add
separate raw-file links.

Each build also writes `global-search.json` at the site root. It is a compact
manifest of the built HTML pages, intended for the central NMOS index to merge
into the static global search at
`https://specs.amwa.tv/new/nmos/global-search/`.

## Local preview

From a checked-out documentation repository, run the shared preview helper
(the repositories and this toolkit can be sibling directories):

```sh
../amwa-spec-docs/scripts/local-render.sh
```

It copies the current working tree to a temporary directory, prepares and
builds it there, and serves the completed site. It watches the working tree and
rebuilds automatically when source files change. The working tree is not
modified. Set `PORT`, `VENV_DIR`, or `RAML_DIR` to customize the local tools;
set `KEEP_RENDER=1` to retain the generated temporary site after stopping the
server. The preview includes `spec.json` at its site root.

For a build without starting a server:

```sh
TOOLKIT_DIR=../amwa-spec-docs \
  bash ../amwa-spec-docs/scripts/prepare-docs.sh
zensical build --clean
```

The preparation step itself is normally run from the caller repository root.

## Development and release policy

The first consumers may temporarily use `@main`/`toolkit-ref: main` while this
repository is being established. Once the interface is stable, publish a
release tag (for example `v1.0.0`) and migrate consumers to that tag or, for
strongest reproducibility, to a commit SHA. Changes to the reusable workflow
should be treated as compatibility-sensitive because callers execute it
remotely.
