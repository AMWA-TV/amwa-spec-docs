import importlib.util
from pathlib import Path
import unittest


SCRIPT = Path(__file__).parents[1] / "scripts" / "ensure-mermaid-config.py"
SPEC = importlib.util.spec_from_file_location("ensure_mermaid_config", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class MermaidConfigTests(unittest.TestCase):
    def test_adds_native_fence_to_existing_superfences_table(self):
        config = (
            "[project.markdown_extensions.pymdownx.superfences]\n"
            "\n[project.theme]\nfeatures = []\n"
        )

        updated = MODULE.ensure_mermaid_config(config)

        self.assertIn("custom_fences = [{ name = \"mermaid\"", updated)
        self.assertIn("[project.theme]", updated)
        self.assertEqual(MODULE.ensure_mermaid_config(updated), updated)

    def test_adds_dotted_setting_to_markdown_extensions_table(self):
        config = "[project.markdown_extensions]\nfoo = true\n\n[project.theme]\n"

        updated = MODULE.ensure_mermaid_config(config)

        self.assertIn(
            "pymdownx.superfences.custom_fences = [{ name = \"mermaid\"",
            updated,
        )
        self.assertIn("foo = true", updated)

    def test_adds_superfences_table_when_no_markdown_extensions_exist(self):
        config = '[project]\nsite_name = "Example"\n'

        updated = MODULE.ensure_mermaid_config(config)

        self.assertIn("[project.markdown_extensions.pymdownx.superfences]", updated)
        self.assertIn('name = "mermaid"', updated)

    def test_preserves_and_extends_existing_custom_fences(self):
        config = (
            "[project.markdown_extensions.pymdownx.superfences]\n"
            "custom_fences = [\n"
            '  { name = "plantuml", class = "plantuml", format = "render" }\n'
            "]\n"
        )

        updated = MODULE.ensure_mermaid_config(config)

        self.assertIn('name = "plantuml"', updated)
        self.assertIn('name = "mermaid"', updated)
        self.assertEqual(updated.count("custom_fences ="), 1)

    def test_leaves_existing_mermaid_configuration_unchanged(self):
        config = (
            "[project.markdown_extensions.pymdownx.superfences]\n"
            'custom_fences = [{ name = "mermaid", class = "mermaid", '
            'format = "pymdownx.superfences.fence_code_format" }]\n'
        )

        self.assertEqual(MODULE.ensure_mermaid_config(config), config)


if __name__ == "__main__":
    unittest.main()
