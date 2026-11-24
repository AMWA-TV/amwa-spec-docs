import importlib.util
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

SCRIPT = Path(__file__).parents[1] / "scripts" / "render-spec-status.py"
SPEC = importlib.util.spec_from_file_location("render_spec_status", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class SpecStatusRenderingTests(unittest.TestCase):
    def test_places_status_below_the_front_page_title(self):
        rendered = MODULE.add_status("# Example specification\n\nIntro text.\n", "AMWA Specification")

        self.assertEqual(
            rendered,
            "# Example specification\n\n**Status:** AMWA Specification\n\nIntro text.\n",
        )

    def test_updates_an_existing_status_without_duplicating_it(self):
        rendered = MODULE.add_status(
            "# Example\n\n**Status:** Old status\n\nBody\n",
            "Work In Progress",
        )

        self.assertEqual(
            rendered,
            "# Example\n\n**Status:** Work In Progress\n\nBody\n",
        )

    def test_reads_status_from_current_metadata_when_ref_has_none(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "historical" / "spec.yml"
            source.parent.mkdir()
            source.write_text("name: Historical\n", encoding="utf-8")
            metadata = root / "current"
            metadata.mkdir()
            (metadata / "spec.yml").write_text(
                "status: AMWA Specification (Stable)\n", encoding="utf-8"
            )

            self.assertEqual(
                MODULE.read_status(source, metadata),
                "AMWA Specification (Stable)",
            )

    def test_prefers_status_from_the_rendered_ref(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "historical" / "spec.yml"
            source.parent.mkdir()
            source.write_text("status: Deprecated\n", encoding="utf-8")
            metadata = root / "current"
            metadata.mkdir()
            (metadata / "spec.yml").write_text(
                "status: AMWA Specification (Stable)\n", encoding="utf-8"
            )

            self.assertEqual(MODULE.read_status(source, metadata), "Deprecated")

    def test_returns_no_status_when_metadata_has_no_status(self):
        with TemporaryDirectory() as directory:
            source = Path(directory) / "spec.yml"
            source.write_text("name: Example\n", encoding="utf-8")

            self.assertIsNone(MODULE.read_status(source))


if __name__ == "__main__":
    unittest.main()
