import tempfile
import unittest
from pathlib import Path

from codex_harness.checks.python_ruff import analyze_source
from codex_harness.checks.ruff_metrics import METRIC_CODES, build_options, load_limits

from .helpers import TemporaryConfigMixin


class RuffCompatibilityTests(TemporaryConfigMixin, unittest.TestCase):
    def test_global_metric_codes_and_limits_are_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            self.use_config(Path(directory) / "config" / "quality.toml")

            limits = load_limits()

            self.assertEqual(
                limits,
                {"C901": 10, "PLR0912": 12, "PLR0915": 50, "PLR1702": 4},
            )
            self.assertEqual(METRIC_CODES, frozenset(limits))
            options = build_options(limits)
            self.assertIn("C901,PLR0912,PLR0915,PLR1702", options)

    def test_normal_ruff_pass_still_reports_target_diagnostics(self) -> None:
        path = Path(tempfile.gettempdir()) / "ruff_compatibility.py"

        findings = analyze_source("import os\n", path)

        self.assertEqual([(item.code, item.line) for item in findings], [("F401", 1)])
