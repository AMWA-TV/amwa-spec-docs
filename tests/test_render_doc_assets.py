import importlib.util
from pathlib import Path
import unittest


SCRIPT = Path(__file__).parents[1] / "scripts" / "render-doc-assets.py"
SPEC = importlib.util.spec_from_file_location("render_doc_assets", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class JsonRenderingTests(unittest.TestCase):
    def test_open_object_summary_has_no_collapsed_closing_brace(self):
        rendered = MODULE.render_json({"code": {"type": "integer"}})

        self.assertIn('<details class="json-node" open>', rendered)
        self.assertIn('{ <span class="json-fold">…</span>', rendered)
        self.assertIn('<span class="json-collapsed-close">}</span>', rendered)
        self.assertIn('<span class="json-key">&quot;code&quot;</span>: {', rendered)
        self.assertIn('<span class="json-key">&quot;type&quot;</span>: ', rendered)

    def test_controls_and_nested_folding_are_rendered(self):
        rendered = MODULE.render_json({"required": ["code"], "properties": {}})

        self.assertIn('data-json-action="expand"', rendered)
        self.assertIn('data-json-action="collapse"', rendered)
        self.assertGreaterEqual(rendered.count('class="json-node"'), 3)
        self.assertIn('class="json-children"', rendered)


if __name__ == "__main__":
    unittest.main()
