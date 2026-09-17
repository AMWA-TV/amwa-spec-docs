#!/usr/bin/env python3
"""Build a Zensical site with Mike and add generated site metadata before commit.

Mike's deploy command performs its own Zensical build. Files added to ``site``
by a separate step before invoking ``mike deploy`` are therefore discarded. This
wrapper runs the metadata generators inside Mike's deploy transaction, after
Mike has built the site and before it copies the site tree to gh-pages.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from mike import commands, driver, git_utils, utils


def run_metadata_generators(toolkit_dir: str) -> None:
    toolkit = Path(toolkit_dir).resolve()
    scripts = toolkit / "scripts"
    subprocess.run(
        [sys.executable, str(scripts / "render-spec-json.py")],
        check=True,
    )
    subprocess.run(
        [sys.executable, str(scripts / "render-search-index.py")],
        check=True,
    )
    if not os.path.isfile("site/global-search.json"):
        raise RuntimeError("global-search.json was not generated")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version")
    parser.add_argument("--toolkit-dir", default=os.environ.get("TOOLKIT_DIR", "."))
    parser.add_argument("--config-file", default=None)
    parser.add_argument("--remote", default="origin")
    parser.add_argument("--branch", default="gh-pages")
    parser.add_argument("--push", action="store_true")
    args = parser.parse_args()

    config_file = args.config_file
    config = utils.load_config(config_file)
    with driver.handle_empty_commit():
        with commands.deploy(
            config,
            args.version,
            branch=args.branch,
        ):
            with utils.inject_plugin(config_file) as build_config:
                utils.build(build_config, args.version)
            run_metadata_generators(args.toolkit_dir)

    if args.push:
        git_utils.push_branch(args.remote, args.branch)


if __name__ == "__main__":
    main()
