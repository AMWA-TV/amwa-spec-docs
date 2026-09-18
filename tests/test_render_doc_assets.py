import importlib.util
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest


SCRIPT = Path(__file__).parents[1] / "scripts" / "render-doc-assets.py"
SPEC = importlib.util.spec_from_file_location("render_doc_assets", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class JsonRenderingTests(unittest.TestCase):
    def test_json_uses_the_foldable_source_viewer(self):
        rendered = MODULE.render_json({"code": {"type": "integer"}})

        self.assertIn('<div class="json-viewer"', rendered)
        self.assertIn('data-language="json"', rendered)
        self.assertIn('data-source=', rendered)
        self.assertIn('value="folding" selected', rendered)
        self.assertIn('value="raw"', rendered)
        self.assertNotIn("Raw file", rendered)
        self.assertNotIn("Resolved JSON file", rendered)

    def test_controls_and_nested_folding_are_rendered(self):
        rendered = MODULE.render_json({"required": ["code"], "properties": {}})

        self.assertIn('data-source-action="expand"', rendered)
        self.assertIn('data-source-action="collapse"', rendered)
        self.assertIn('class="source-editor"', rendered)
        self.assertIn('aria-label="Foldable JSON source"', rendered)


class RamlRenderingTests(unittest.TestCase):
    def test_legacy_raml_is_published_as_source(self):
        with TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "NodeAPI.raml"
            source.write_text("#%RAML 0.8\n\ntitle: Node\n", encoding="utf-8")

            version = MODULE.raml_version(source)
            rendered = MODULE.raw_raml_page(source, Path("NodeAPI.raml"), version)

        self.assertEqual(version, "0.8")
        self.assertIn("not supported by the shared HTML renderer", rendered)
        self.assertIn("```raml", rendered)
        self.assertIn("title: Node", rendered)


if __name__ == "__main__":
    unittest.main()
