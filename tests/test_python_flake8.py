import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from codex_harness.checks.python_flake8 import parse_output, runner


class Flake8AdapterTests(unittest.TestCase):
    def test_malformed_output_fails_closed(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "malformed diagnostic"):
            parse_output("not-a-diagnostic\n", 1, Path("subject.py"))

    def test_missing_plugin_error_fails_closed(self) -> None:
        result = subprocess.CompletedProcess(
            args=[],
            returncode=1,
            stdout="",
            stderr="required plugin is not installed",
        )
        with (
            tempfile.TemporaryDirectory() as directory,
            mock.patch.object(runner.subprocess, "run", return_value=result),
            self.assertRaisesRegex(RuntimeError, "required plugin"),
        ):
            runner.run_check(
                "def sample():\n    pass\n", Path(directory) / "case.py", 80
            )
