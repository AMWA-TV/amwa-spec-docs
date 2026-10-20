import importlib.util
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "scripts" / "migrate-repositories.py"
SPEC = importlib.util.spec_from_file_location("migrate_repositories", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class MappingTests(unittest.TestCase):
    def test_maps_numeric_legacy_page_to_numeric_release_tree(self):
        suffix = MODULE.map_legacy_path(
            "is-06",
            "https://specs.amwa.tv/is-06/releases/v1.0.1/docs/1.0._Overview.html",
            default_version="v1.0.1",
            docs_by_version={"v1.0.1": ["1.0. Overview", "APIs"]},
        )
        self.assertEqual(suffix, "/v1.0.1/1.0.%20Overview/")

    def test_maps_numeric_legacy_page_to_unnumbered_branch_tree(self):
        suffix = MODULE.map_legacy_path(
            "is-06",
            "https://specs.amwa.tv/is-06/branches/v1.0.x/docs/2.0._APIs.html",
            default_version="v1.0.1",
            docs_by_version={"v1.0.x": ["APIs"], "v1.0.1": ["2.0. APIs"]},
        )
        self.assertEqual(suffix, "/v1.0.x/APIs/")

    def test_maps_raw_root_json_to_default_examples_tree(self):
        suffix = MODULE.map_legacy_path(
            "is-10",
            "https://specs.amwa.tv/is-10/auth-metadata-get-200.json",
            default_version="v1.0.1",
            docs_by_version={"v1.0.1": []},
        )
        self.assertEqual(suffix, "/v1.0.1/examples/auth-metadata-get-200.json")

    def test_maps_non_versioned_docs_to_site_root(self):
        suffix = MODULE.map_legacy_path(
            "info-002",
            "https://specs.amwa.tv/info-002/docs/Overview.html",
            default_version="",
            docs_by_version={"": ["Overview", "APIs"]},
            versioned=False,
        )
        self.assertEqual(suffix, "/Overview/")

    def test_maps_non_versioned_assets_without_version_directory(self):
        cases = {
            "https://specs.amwa.tv/info-002/APIs/NodeAPI.html": "/APIs/NodeAPI/",
            "https://specs.amwa.tv/info-002/APIs/schemas/node.json": "/schemas/node.json",
            "https://specs.amwa.tv/info-002/example.json": "/examples/example.json",
            "https://specs.amwa.tv/info-002/docs/images/logo.png": "/images/logo.png",
        }
        for legacy_url, expected in cases.items():
            with self.subTest(legacy_url=legacy_url):
                self.assertEqual(
                    MODULE.map_legacy_path(
                        "info-002",
                        legacy_url,
                        default_version="",
                        docs_by_version={"": []},
                        versioned=False,
                    ),
                    expected,
                )

    def test_leaves_global_site_chrome_unmapped(self):
        for path in (
            "/is-06/releases/",
            "/is-06/branches/",
            "/is-06/codemirror/lib/codemirror.js",
            "/is-06/json-formatter.js",
        ):
            with self.subTest(path=path):
                self.assertEqual(
                    MODULE.map_legacy_path(
                        "is-06",
                        "https://specs.amwa.tv" + path,
                        default_version="v1.0.1",
                        docs_by_version={"v1.0.1": []},
                    ),
                    "",
                )


class FileUpdateTests(unittest.TestCase):
    def test_updates_non_versioned_workflow(self):
        source = """name: Documentation

jobs:
  docs:
    uses: AMWA-TV/amwa-spec-docs/.github/workflows/docs.yml@main
    with:
      versioned: false
      site-name: info-002
      public-docs-root: https://specs.amwa.tv/new/info-002
"""
        updated = MODULE.update_workflow_text(source, "info-002")
        self.assertIn("versioned: false", updated)
        self.assertIn("public-docs-root: https://specs.amwa.tv/info-002", updated)
        self.assertIn("upload-prefix: ''", updated)
        self.assertIn("legacy-mapping: .docs/legacy-mappings.csv", updated)
        self.assertNotIn("https://specs.amwa.tv/new/info-002", updated)

    def test_updates_workflow_without_removing_render_workflow_reference(self):
        source = """name: Documentation\n\n# Experimental shared-toolkit rendering. The existing render.yml workflow and\n# .render pipeline remain active until the new output has been accepted.\n\njobs:\n  docs:\n    uses: AMWA-TV/amwa-spec-docs/.github/workflows/docs.yml@main\n    with:\n      versioned: true\n      site-name: is-06\n      public-docs-root: https://specs.amwa.tv/new/is-06\n"""
        updated = MODULE.update_workflow_text(source, "is-06")
        self.assertIn("public-docs-root: https://specs.amwa.tv/is-06", updated)
        self.assertIn("upload-prefix: ''", updated)
        self.assertIn("legacy-mapping: .docs/legacy-mappings.csv", updated)
        self.assertNotIn("Experimental shared-toolkit", updated)
        self.assertNotIn("https://specs.amwa.tv/new/is-06", updated)

    def test_removes_only_legacy_badge(self):
        source = (
            "[![Zensical Render Status](docs)](docs)\n"
            "[![Legacy Render Status](legacy)](legacy)\n"
            "\n"
        )
        updated = MODULE.update_readme_text(source)
        self.assertIn("Zensical Render Status", updated)
        self.assertNotIn("Legacy Render Status", updated)


if __name__ == "__main__":
    unittest.main()
