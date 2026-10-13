import importlib.util
from pathlib import Path
import unittest


SCRIPT = Path(__file__).parents[1] / "scripts" / "generate_html_bridges.py"
SPEC = importlib.util.spec_from_file_location("generate_html_bridges", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class BridgeTargetTests(unittest.TestCase):
    def row(self, target):
        return {"target_url": target}

    def test_accepts_canonical_target_tree(self):
        target = MODULE.target_for(
            self.row("https://specs.amwa.tv/is-08/v1.0.1/Overview/"),
            "https://specs.amwa.tv/is-08/",
        )
        self.assertEqual(target, "https://specs.amwa.tv/is-08/v1.0.1/Overview/")

    def test_migrates_legacy_target_tree_to_canonical_prefix(self):
        target = MODULE.target_for(
            self.row("https://specs.amwa.tv/new/is-08/v1.0.1/Overview/"),
            "https://specs.amwa.tv/is-08/",
        )
        self.assertEqual(target, "https://specs.amwa.tv/is-08/v1.0.1/Overview/")

    def test_rejects_target_from_another_site_tree(self):
        with self.assertRaisesRegex(ValueError, "outside the expected"):
            MODULE.target_for(
                self.row("https://specs.amwa.tv/is-05/v1.0.1/Overview/"),
                "https://specs.amwa.tv/is-08/",
            )
