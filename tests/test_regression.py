import json
import tempfile
import unittest
from pathlib import Path

from codex_harness.checks.regression import check_snapshot

from .helpers import TemporaryConfigMixin, function_source


class FunctionLengthRegressionTests(TemporaryConfigMixin, unittest.TestCase):
    def compare(self, before_length: int, after_length: int):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.use_config(root / "config" / "quality.toml")
            source_path = root / "subject.py"
            source_path.write_text(function_source(after_length), encoding="utf-8")
            snapshot_path = root / "snapshot.json"
            snapshot_path.write_text(
                json.dumps(
                    {
                        "files": {
                            str(source_path): {
                                "exists": True,
                                "content": function_source(before_length),
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            return check_snapshot(snapshot_path)

    def test_new_violation_is_blocked(self) -> None:
        findings = self.compare(80, 81)
        self.assertEqual(
            [(item.rule, item.value) for item in findings], [("CFQ001", 81)]
        )

    def test_existing_violation_without_growth_passes(self) -> None:
        self.assertEqual(self.compare(81, 81), [])

    def test_existing_violation_growth_is_blocked(self) -> None:
        findings = self.compare(81, 82)
        self.assertEqual(
            [(item.rule, item.value) for item in findings], [("CFQ001", 82)]
        )

    def test_existing_violation_improvement_passes(self) -> None:
        self.assertEqual(self.compare(82, 81), [])
