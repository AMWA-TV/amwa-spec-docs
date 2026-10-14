import csv
import importlib.util
from pathlib import Path
import tempfile
import unittest


SCRIPT = Path(__file__).parents[1] / "scripts" / "generate_html_bridges.py"
SPEC = importlib.util.spec_from_file_location("generate_html_bridges", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

COPY_SCRIPT = Path(__file__).parents[1] / "scripts" / "copy_legacy_assets.py"
COPY_SPEC = importlib.util.spec_from_file_location("copy_legacy_assets", COPY_SCRIPT)
assert COPY_SPEC and COPY_SPEC.loader
COPY_MODULE = importlib.util.module_from_spec(COPY_SPEC)
COPY_SPEC.loader.exec_module(COPY_MODULE)


class LegacyAssetTests(unittest.TestCase):
    def test_copies_asset_from_canonical_site_tree(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            site = root / "site"
            canonical = site / "latest" / "schemas" / "example.json"
            canonical.parent.mkdir(parents=True)
            canonical.write_bytes(b'{"ok": true}\n')
            csv_path = root / "mapping.csv"
            with csv_path.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.writer(stream)
                writer.writerow([
                    "legacy_url", "legacy_status", "target_url",
                    "target_status_current", "mapping_class",
                    "legacy_content_type", "legacy_location",
                    "target_content_type", "target_effective_url",
                ])
                writer.writerow([
                    "https://specs.amwa.tv/site/branches/main/schemas/example.json",
                    "200",
                    "https://specs.amwa.tv/site/latest/schemas/example.json",
                    "200",
                    "confirmed-main",
                    "application/json",
                    "",
                    "application/json",
                    "https://specs.amwa.tv/site/latest/schemas/example.json",
                ])

            copied = COPY_MODULE.copy_assets(
                csv_path,
                site,
                "/site/",
                "https://specs.amwa.tv/site/",
            )

            self.assertEqual(copied, 1)
            self.assertEqual(
                (site / "branches/main/schemas/example.json").read_bytes(),
                b'{"ok": true}\n',
            )


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
