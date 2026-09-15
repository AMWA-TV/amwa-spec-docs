import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


SCRIPT = Path(__file__).parents[1] / "scripts" / "render-spec-json.py"
SPEC = importlib.util.spec_from_file_location("render_spec_json", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class SpecJsonRenderingTests(unittest.TestCase):
    def test_renders_yaml_mapping_as_json(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "spec.yml"
            destination = root / "site" / "spec.json"
            source.write_text(
                "amwa_id: IN-001\nstatus: Work In Progress\nshow_in_index: false\n",
                encoding="utf-8",
            )

            MODULE.render_spec_json(source, destination)

            self.assertEqual(
                json.loads(destination.read_text(encoding="utf-8")),
                {
                    "amwa_id": "IN-001",
                    "status": "Work In Progress",
                    "show_in_index": False,
                },
            )

    def test_includes_readme_intro_bullets(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "spec.yml"
            source.write_text("name: Example\n", encoding="utf-8")
            (root / "README.md").write_text(
                """<!-- INTRO-START -->

### What does it do?

- Does one thing
- Does another thing

### Why does it matter?

- It helps users

### How does it work?

- By using a clear process

<!-- INTRO-END -->
""",
                encoding="utf-8",
            )
            destination = root / "site" / "spec.json"

            MODULE.render_spec_json(source, destination)

            self.assertEqual(
                json.loads(destination.read_text(encoding="utf-8"))["intro"],
                {
                    "what_does_it_do": ["Does one thing", "Does another thing"],
                    "why_does_it_matter": ["It helps users"],
                    "how_does_it_work": ["By using a clear process"],
                },
            )

    def test_rejects_non_mapping_yaml(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "spec.yml"
            source.write_text("- not a mapping\n", encoding="utf-8")

            with self.assertRaises(TypeError):
                MODULE.render_spec_json(source, root / "site" / "spec.json")


if __name__ == "__main__":
    unittest.main()
