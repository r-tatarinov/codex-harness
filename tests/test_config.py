import tempfile
import unittest
from pathlib import Path

from codex_harness.checks.code_quality import config

from .helpers import TemporaryConfigMixin


class ConfigTests(TemporaryConfigMixin, unittest.TestCase):
    def test_repository_config_matches_packaged_defaults(self) -> None:
        repository_config = Path(__file__).parents[1] / "config" / "quality.toml"
        self.assertEqual(
            repository_config.read_text(encoding="utf-8"),
            config.DEFAULT_CONFIG.read_text(encoding="utf-8"),
        )

    def test_missing_config_is_created_with_current_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".codex" / "harness" / "config" / "quality.toml"
            self.use_config(path)

            loaded = config.load_config()

            self.assertTrue(path.is_file())
            self.assertEqual(loaded["verification"]["max_attempts"], 3)
            self.assertEqual(loaded["python"]["functions"]["max_lines"], 80)
            self.assertEqual(
                loaded["python"]["ruff"],
                {
                    "max_complexity": 10,
                    "max_branches": 12,
                    "max_statements": 50,
                    "max_nested_blocks": 4,
                },
            )

    def test_existing_config_overrides_defaults_without_rewrite(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "quality.toml"
            path.write_text("[python.functions]\nmax_lines = 90\n", encoding="utf-8")
            self.use_config(path)

            loaded = config.load_config()

            self.assertEqual(loaded["python"]["functions"]["max_lines"], 90)
            self.assertEqual(loaded["verification"]["max_attempts"], 3)
            self.assertEqual(
                path.read_text(encoding="utf-8"),
                "[python.functions]\nmax_lines = 90\n",
            )
