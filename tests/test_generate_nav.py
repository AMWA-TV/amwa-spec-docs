import importlib.util
import os
from pathlib import Path
import tempfile
import unittest

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - supported test runtimes use 3.11+
    tomllib = None


SCRIPT = Path(__file__).parents[1] / "scripts" / "generate-nav.py"
SPEC = importlib.util.spec_from_file_location("generate_nav", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class NavigationGenerationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.original_directory = os.getcwd()
        os.chdir(self.directory.name)
        Path("docs").mkdir()
        self.addCleanup(self._restore_directory)

    def _restore_directory(self):
        os.chdir(self.original_directory)
        self.directory.cleanup()

    def write(self, path, content=""):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def test_generates_ordered_nested_navigation_with_decoded_paths(self):
        self.write(
            "docs/README.md",
            """### Introduction

- [Overview](Overview.md)

### APIs

- [General](APIs.md)
  - [Client Side Implementation](APIs%20-%20Client%20Side%20Implementation.md)
  - [Server Side Implementation](APIs%20-%20Server%20Side%20Implementation.md)

### Miscellaneous

- [Upgrade Path](Upgrade%20Path.md)
""",
        )
        for path in (
            "Overview.md",
            "APIs.md",
            "APIs - Client Side Implementation.md",
            "APIs - Server Side Implementation.md",
            "Upgrade Path.md",
        ):
            self.write(Path("docs") / path)
        self.write(
            "zensical.toml",
            """[project]
site_name = "Example"
nav = ["old.md"]
site_url = "https://example.test/"
""",
        )

        MODULE.main()

        config = Path("zensical.toml").read_text(encoding="utf-8")
        self.assertIn('"Client Side Implementation" = "APIs - Client Side Implementation.md"', config)
        self.assertLess(config.index('"Overview"'), config.index('"General"'))
        self.assertLess(config.index('"General"'), config.index('"Upgrade Path"'))
        self.assertNotIn('nav = ["old.md"]', config)

        if tomllib is not None:
            parsed = tomllib.loads(config)
            self.assertEqual(
                parsed["project"]["nav"],
                [
                    "index.md",
                    {"Introduction": [{"Overview": "Overview.md"}]},
                    {
                        "APIs": [
                            {
                                "General": [
                                    "APIs.md",
                                    {
                                        "Client Side Implementation": (
                                            "APIs - Client Side Implementation.md"
                                        )
                                    },
                                    {
                                        "Server Side Implementation": (
                                            "APIs - Server Side Implementation.md"
                                        )
                                    },
                                ]
                            }
                        ]
                    },
                    {"Miscellaneous": [{"Upgrade Path": "Upgrade Path.md"}]},
                ],
            )

    def test_includes_generated_asset_trees_in_explicit_navigation(self):
        self.write(
            "docs/README.md",
            """### APIs

- [General](APIs.md)
""",
        )
        self.write("docs/APIs.md")
        self.write(
            "docs/APIs/index.md",
            """# APIs

- [ConnectionAPI](ConnectionAPI.md)
""",
        )
        self.write("docs/APIs/ConnectionAPI.md")
        self.write(
            "docs/schemas/index.md",
            """# JSON Schemas

- [connection](connection.md)
""",
        )
        self.write("docs/schemas/connection.md")
        self.write(
            "docs/examples/index.md",
            """# Examples

- [basic](basic.md)
""",
        )
        self.write("docs/examples/basic.md")
        self.write("zensical.toml", "[project]\nsite_name = \"Example\"\n")

        MODULE.main()

        if tomllib is not None:
            nav = tomllib.loads(Path("zensical.toml").read_text())["project"]["nav"]
            self.assertEqual(nav[1], {"APIs": [{"General": "APIs.md"}]})
            self.assertEqual(
                nav[2],
                {
                    "API Definitions": [
                        "APIs/index.md",
                        {"ConnectionAPI": "APIs/ConnectionAPI.md"},
                    ]
                },
            )
            self.assertEqual(
                nav[3],
                {
                    "JSON Schemas": [
                        "schemas/index.md",
                        {"connection": "schemas/connection.md"},
                    ]
                },
            )
            self.assertEqual(
                nav[4],
                {
                    "Examples": [
                        "examples/index.md",
                        {"basic": "examples/basic.md"},
                    ]
                },
            )

    def test_accepts_unheaded_document_links(self):
        self.write(
            "docs/README.md",
            """<!-- Navigation notes -->

- [Document](Document.md)
""",
        )
        self.write("docs/Document.md")

        sections = MODULE.parse_navigation()

        self.assertEqual(
            sections,
            [("Documentation", [{"label": "Document", "path": "Document.md", "children": []}])],
        )

    def test_skips_missing_targets_and_keeps_external_targets(self):
        self.write(
            "docs/README.md",
            """### Links

- [Present](present.md)
- [Missing](missing.md)
- [Generated directory](generated/)
- [External](https://example.test/reference)
""",
        )
        self.write("docs/present.md")
        self.write("docs/generated/index.md")
        self.write("zensical.toml", "[project]\nsite_name = \"Example\"\n")

        sections = MODULE.parse_navigation()

        self.assertEqual(len(sections), 1)
        self.assertEqual(
            [node["label"] for node in sections[0][1]],
            ["Present", "Generated directory", "External"],
        )
        self.assertEqual(sections[0][1][1]["path"], "generated/index.md")
        self.assertEqual(sections[0][1][2]["path"], "https://example.test/reference")

    def test_does_not_change_config_without_navigation_source(self):
        original = "[project]\nsite_name = \"Example\"\n"
        self.write("zensical.toml", original)

        MODULE.main()

        self.assertEqual(Path("zensical.toml").read_text(encoding="utf-8"), original)


if __name__ == "__main__":
    unittest.main()
