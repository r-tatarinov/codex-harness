import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from .helpers import function_source


class HookCycleTests(unittest.TestCase):
    def run_hook(self, executable: str, event: dict, home: Path):
        environment = os.environ.copy()
        environment["HOME"] = str(home)
        return subprocess.run(
            [str(Path(sys.executable).parent / executable)],
            input=json.dumps(event),
            text=True,
            capture_output=True,
            env=environment,
            check=False,
            timeout=30,
        )

    def event(self, target: Path, tool_use_id: str) -> dict:
        return {
            "session_id": "test-session",
            "turn_id": "test-turn",
            "tool_use_id": tool_use_id,
            "tool_name": "apply_patch",
            "cwd": str(target.parent),
            "tool_input": {
                "command": (f"*** Begin Patch\n*** Add File: {target}\n*** End Patch\n")
            },
        }

    def test_full_hook_cycle_passes_at_80_and_blocks_at_81(self) -> None:
        with (
            tempfile.TemporaryDirectory() as home_directory,
            tempfile.TemporaryDirectory() as target_directory,
        ):
            home = Path(home_directory)
            root = Path(target_directory)

            passing = root / "passing.py"
            passing_event = self.event(passing, "passing-patch")
            pre = self.run_hook("codex-harness-pre-tool", passing_event, home)
            self.assertEqual((pre.returncode, pre.stdout, pre.stderr), (0, "", ""))
            passing.write_text(function_source(80), encoding="utf-8")
            post = self.run_hook("codex-harness-post-tool", passing_event, home)
            self.assertEqual((post.returncode, post.stdout, post.stderr), (0, "", ""))

            blocking = root / "blocking.py"
            blocking_event = self.event(blocking, "blocking-patch")
            pre = self.run_hook("codex-harness-pre-tool", blocking_event, home)
            self.assertEqual((pre.returncode, pre.stdout, pre.stderr), (0, "", ""))
            blocking.write_text(function_source(81), encoding="utf-8")
            post = self.run_hook("codex-harness-post-tool", blocking_event, home)
            response = json.loads(post.stdout)
            self.assertEqual(post.returncode, 0)
            self.assertEqual(response["decision"], "block")
            self.assertIn("CFQ001", response["reason"])
            self.assertIn("Verification attempt 1/3", response["reason"])

            config = home / ".codex" / "harness" / "config" / "quality.toml"
            self.assertTrue(config.is_file())
