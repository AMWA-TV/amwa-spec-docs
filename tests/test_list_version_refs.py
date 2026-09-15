import importlib.util
from pathlib import Path
import unittest


SCRIPT = Path(__file__).parents[1] / "scripts" / "list-version-refs.py"
SPEC = importlib.util.spec_from_file_location("list_version_refs", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class VersionRefTests(unittest.TestCase):
    def test_selects_legacy_release_and_branch_patterns(self):
        lines = [
            "a refs/tags/v1.0",
            "b refs/tags/v1.2.0",
            "c refs/tags/v1.2.0^{}",
            "d refs/tags/workshop-end",
            "e refs/heads/v1.2-dev",
            "f refs/heads/v1.1.x",
            "g refs/heads/publish-example",
            "h refs/heads/feature/example",
            "i refs/heads/main",
        ]

        self.assertEqual(
            MODULE.matching_refs(lines),
            [
                ("branch", "publish-example"),
                ("branch", "v1.1.x"),
                ("branch", "v1.2-dev"),
                ("tag", "v1.0"),
                ("tag", "v1.2.0"),
            ],
        )

    def test_patterns_can_be_overridden_for_main_based_repositories(self):
        lines = [
            "a refs/heads/main",
            "b refs/heads/publish-example",
            "c refs/heads/v1.0-dev",
        ]

        self.assertEqual(
            MODULE.matching_refs(
                lines,
                release_pattern="",
                branch_pattern=r"^main$|^publish-",
            ),
            [("branch", "main"), ("branch", "publish-example")],
        )


if __name__ == "__main__":
    unittest.main()
