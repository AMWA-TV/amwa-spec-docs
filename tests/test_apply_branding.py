import os
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

SCRIPT = Path(__file__).parents[1] / "scripts" / "apply-branding.sh"
TOOLKIT_ROOT = Path(__file__).parents[1]


class BrandingConfigTests(unittest.TestCase):
    def test_registers_json_viewer_assets_without_duplicates(self):
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "zensical.toml").write_text(
                '[project]\n'
                'site_name = "Test specification"\n'
                'extra_css = ["stylesheets/custom.css"]\n'
                'extra_javascript = ["javascripts/custom.js"]\n',
                encoding="utf-8",
            )
            env = os.environ.copy()
            env.update(
                {
                    "GITHUB_REPOSITORY": "AMWA-TV/is-04",
                    "TOOLKIT_DIR": str(TOOLKIT_ROOT),
                }
            )

            for _ in range(2):
                subprocess.run(
                    ["bash", str(SCRIPT)],
                    cwd=root,
                    env=env,
                    check=True,
                    capture_output=True,
                    text=True,
                )

            config = (root / "zensical.toml").read_text(encoding="utf-8")
            self.assertEqual(config.count('"stylesheets/extra.css"'), 1)
            self.assertEqual(config.count('"javascripts/json-viewer.js"'), 1)
            self.assertIn('"stylesheets/amwa-branding.css"', config)
            self.assertIn('"javascripts/amwa-branding.js"', config)
            self.assertIn('"stylesheets/custom.css"', config)
            self.assertIn('"javascripts/custom.js"', config)


if __name__ == "__main__":
    unittest.main()
