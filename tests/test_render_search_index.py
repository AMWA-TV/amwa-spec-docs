import importlib.util
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "render-search-index.py"
SPEC = importlib.util.spec_from_file_location("render_search_index", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class SearchManifestTests(unittest.TestCase):
    def test_extracts_page_content_and_excludes_site_chrome(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            page = root / "Overview" / "index.html"
            page.parent.mkdir()
            page.write_text(
                """<html><head><title>Overview - Example</title></head>
                <body><nav>Navigation noise</nav><main>
                <h1>Overview</h1><p>Useful documentation text.</p>
                </main><footer>Footer noise</footer></body></html>""",
                encoding="utf-8",
            )
            MODULE.SITE = root
            MODULE.PUBLIC_ROOT = "https://specs.amwa.tv/new/example"
            MODULE.REPOSITORY = "AMWA-TV/example"

            document = MODULE.render_page(page)

            self.assertIsNotNone(document)
            assert document
            self.assertEqual(document["title"], "Overview")
            self.assertIn("Useful documentation text", document["text"])
            self.assertNotIn("Navigation noise", document["text"])
            self.assertNotIn("Footer noise", document["text"])
            self.assertEqual(
                document["url"],
                "https://specs.amwa.tv/new/example/latest/Overview/",
            )


if __name__ == "__main__":
    unittest.main()
