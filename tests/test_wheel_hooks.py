import concurrent.futures
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from installation import HookScenario, WheelInstallation


class InstalledHookTests(unittest.TestCase):
    installation: WheelInstallation

    @classmethod
    def setUpClass(cls) -> None:
        root = Path(tempfile.mkdtemp(prefix="harness-wheel-tests-"))
        cls.installation = WheelInstallation(root, Path(__file__).resolve().parents[1])
        cls.installation.build()
        print(f"\nInstalled wheel artifacts: {root}", flush=True)

    def setUp(self) -> None:
        self.scenario = HookScenario(self.installation)
        self.addCleanup(self.scenario.directory.cleanup)

    def assert_result(
        self,
        result: subprocess.CompletedProcess[str],
        status: str,
        blocked: bool = False,
    ) -> dict:
        self.assertEqual(result.returncode, 0, result.stderr)
        raw = json.loads(result.stdout)
        specific = raw["hookSpecificOutput"]
        self.assertTrue(specific["additionalContext"].startswith(status + ": "), raw)
        actual = (
            specific.get("permissionDecision") == "deny"
            or raw.get("decision") == "block"
        )
        self.assertEqual(actual, blocked, raw)
        self.assertFalse(
            {"continue", "suppressOutput", "updatedMCPToolOutput"}.intersection(raw)
        )
        return raw

    def prepare(self) -> None:
        self.assert_result(self.scenario.invoke("pre"), "PREPARED")

    def introduce_regression(self) -> None:
        self.prepare()
        self.scenario.file.write_text("import os\nvalue = 2\n", encoding="utf-8")
        self.assert_result(self.scenario.invoke("post"), "CHECK_FAILED", True)

    def test_baseline_pass_and_replay(self) -> None:
        self.prepare()
        snapshot = json.loads(self.scenario.snapshot().read_text())
        self.assertEqual(
            snapshot["files"][str(self.scenario.file)]["content"], "value = 1\n"
        )
        self.scenario.file.write_text("value = 2\n", encoding="utf-8")
        self.assert_result(self.scenario.invoke("post"), "PASS")
        state = self.scenario.state_path().read_bytes()
        self.assert_result(self.scenario.invoke("post"), "PASS")
        self.assertEqual(self.scenario.state_path().read_bytes(), state)
        self.scenario.file.write_text("import sys\n", encoding="utf-8")
        self.assert_result(self.scenario.invoke("post"), "HARNESS_ERROR", True)

    def test_new_regression_and_concurrent_redelivery(self) -> None:
        self.introduce_regression()
        state = self.scenario.state_path().read_bytes()
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: self.scenario.invoke("post"), range(2)))
        for result in results:
            self.assert_result(result, "CHECK_FAILED", True)
        self.assertEqual(self.scenario.state_path().read_bytes(), state)
        self.assertEqual(self.scenario.state()["consecutive_failed_attempts"], 1)

    def test_pre_redelivery_never_recaptures_baseline(self) -> None:
        self.prepare()
        before = self.scenario.snapshot().read_bytes()
        self.assert_result(self.scenario.invoke("pre"), "PREPARED")
        self.assertEqual(self.scenario.snapshot().read_bytes(), before)
        self.scenario.file.write_text("value = 2\n", encoding="utf-8")
        self.assert_result(self.scenario.invoke("pre"), "HARNESS_ERROR", True)
        self.assertEqual(self.scenario.snapshot().read_bytes(), before)

    def test_import_and_runtime_failures(self) -> None:
        for source in [
            "raise ImportError('injected startup failure')\n",
            "raise SystemExit(0)\n",
            "class HookRuntime:\n    def execute(self, raw, name):\n        raise RuntimeError('injected runtime failure')\n",
        ]:
            with (
                self.subTest(source=source),
                self.installation.replace_module("hooks/runtime.py", source),
            ):
                for name in ("pre", "post"):
                    self.assert_result(
                        self.scenario.invoke(name), "HARNESS_ERROR", True
                    )

    def test_invalid_input(self) -> None:
        for name in ("pre", "post"):
            for payload in ("{", "[]", "null", "{}", '{"hook_event_name":"wrong"}'):
                with self.subTest(name=name, payload=payload):
                    self.assert_result(
                        self.scenario.invoke(name, payload), "HARNESS_ERROR", True
                    )
            self.assert_result(
                self.scenario.invoke(name, closed_input=True), "HARNESS_ERROR", True
            )

    def test_missing_or_corrupt_snapshot(self) -> None:
        self.assert_result(self.scenario.invoke("post"), "HARNESS_ERROR", True)
        self.scenario.next_operation("missing")
        self.prepare()
        self.scenario.snapshot().unlink()
        self.assert_result(self.scenario.invoke("post"), "HARNESS_ERROR", True)
        self.assertEqual(self.scenario.state()["consecutive_failed_attempts"], 0)
        self.scenario.next_operation("corrupt")
        self.prepare()
        self.scenario.snapshot().write_text("{}", encoding="utf-8")
        self.assert_result(self.scenario.invoke("post"), "HARNESS_ERROR", True)

    def test_snapshot_identity_and_coverage(self) -> None:
        for key, value in [("tool_use_id", "other"), ("cwd", "/other"), ("files", {})]:
            with self.subTest(key=key):
                self.scenario.next_operation(key)
                self.prepare()
                path = self.scenario.snapshot()
                snapshot = json.loads(path.read_text())
                snapshot[key] = value
                path.write_text(json.dumps(snapshot), encoding="utf-8")
                self.assert_result(self.scenario.invoke("post"), "HARNESS_ERROR", True)

    def test_configuration_and_unavailable_storage(self) -> None:
        config = self.scenario.root / ".codex/harness/config/quality.toml"
        config.parent.mkdir(parents=True)
        config.write_text("invalid = [", encoding="utf-8")
        self.assert_result(self.scenario.invoke("pre"), "HARNESS_ERROR", True)
        config.unlink()
        state = self.scenario.root / ".codex/harness/state"
        state.write_text("not a directory", encoding="utf-8")
        self.assert_result(self.scenario.invoke("pre"), "HARNESS_ERROR", True)

    def test_infrastructure_failure_preserves_retry(self) -> None:
        self.introduce_regression()
        original = self.scenario.state()
        self.scenario.next_operation("error")
        self.prepare()
        with self.installation.replace_module(
            "checks/analyzers/ruff/adapter.py", "raise ImportError('broken analyzer')\n"
        ):
            self.assert_result(self.scenario.invoke("post"), "HARNESS_ERROR", True)
        current = self.scenario.state()
        self.assertEqual(
            current["consecutive_failed_attempts"],
            original["consecutive_failed_attempts"],
        )
        self.assertEqual(current["last_failure"], original["last_failure"])

    def test_failed_commit_preserves_retry(self) -> None:
        self.introduce_regression()
        self.scenario.next_operation("commit-error")
        self.prepare()
        previous = self.scenario.state_path().read_bytes()
        self.scenario.file.write_text("value = 3\n", encoding="utf-8")
        path = self.installation.package / "checks/storage.py"
        source = (
            path.read_text()
            .replace("self.path = path", "self.path = path")
            .replace(
                "    def write_json(self, value: object) -> None:\n",
                '    def write_json(self, value: object) -> None:\n        if self.path.name == "attempts.json":\n            raise OSError("injected commit failure")\n',
            )
        )
        with self.installation.replace_module("checks/storage.py", source):
            self.assert_result(self.scenario.invoke("post"), "HARNESS_ERROR", True)
        self.assertEqual(self.scenario.state_path().read_bytes(), previous)
        self.assertFalse(list(self.scenario.state_path().parent.glob("*.processing")))
        self.assert_result(self.scenario.invoke("post"), "HARNESS_ERROR", True)

    def test_retry_limit_and_reset(self) -> None:
        for index, module in enumerate(("os", "sys", "json"), 1):
            self.scenario.next_operation(str(index))
            self.prepare()
            with self.scenario.file.open("a", encoding="utf-8") as file:
                file.write(f"import {module}\n")
            self.assert_result(self.scenario.invoke("post"), "CHECK_FAILED", True)
            self.assertEqual(
                self.scenario.state()["consecutive_failed_attempts"], index
            )
        self.scenario.next_operation("denied")
        self.assert_result(self.scenario.invoke("pre"), "CHECK_FAILED", True)
        self.scenario.event["turn_id"] = "new-turn"
        self.prepare()
        self.scenario.file.write_text("value = 4\n", encoding="utf-8")
        self.assert_result(self.scenario.invoke("post"), "PASS")

    def test_success_resets_existing_debt_budget(self) -> None:
        self.introduce_regression()
        self.scenario.next_operation("unrelated")
        self.prepare()
        with self.scenario.file.open("a", encoding="utf-8") as file:
            file.write("other = 3\n")
        self.assert_result(self.scenario.invoke("post"), "PASS")
        self.assertEqual(self.scenario.state()["consecutive_failed_attempts"], 0)
        self.assertIsNone(self.scenario.state()["last_failure"])

    def test_no_change_and_non_python_are_not_applicable(self) -> None:
        self.introduce_regression()
        self.scenario.next_operation("no-change")
        self.prepare()
        self.assert_result(self.scenario.invoke("post"), "NOT_APPLICABLE")
        self.assertEqual(self.scenario.state()["consecutive_failed_attempts"], 1)
        self.scenario.next_operation("readme")
        self.scenario.event["tool_input"][
            "command"
        ] = "*** Begin Patch\n*** Add File: README.md\n+Hello\n*** End Patch"
        self.assert_result(self.scenario.invoke("pre"), "NOT_APPLICABLE")
        self.assert_result(self.scenario.invoke("post"), "NOT_APPLICABLE")
        self.assertEqual(self.scenario.state()["consecutive_failed_attempts"], 1)

    def test_deleted_file_needs_no_analyzer(self) -> None:
        self.prepare()
        self.scenario.file.unlink()
        self.assert_result(self.scenario.invoke("post"), "PASS")

    def test_doctor_healthy_but_unconfirmed_trust(self) -> None:
        self.scenario.configure_hooks()
        result = self.scenario.doctor()
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["result"], "UNKNOWN")
        checks = {item["name"]: item["status"] for item in report["checks"]}
        for name in (
            "Package",
            "Entry points",
            "PreToolUse",
            "PostToolUse",
            "Configuration",
            "Runtime smoke",
        ):
            self.assertEqual(checks[name], "PASS")
        self.assertEqual(checks["Trust"], "UNKNOWN")

    def test_doctor_legacy_async_and_missing_configuration(self) -> None:
        for legacy, asynchronous in [(True, False), (False, True)]:
            with self.subTest(legacy=legacy, asynchronous=asynchronous):
                self.scenario.configure_hooks(legacy=legacy, asynchronous=asynchronous)
                result = self.scenario.doctor()
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertEqual(json.loads(result.stdout)["result"], "FAIL")

    def test_doctor_broken_installed_package(self) -> None:
        self.scenario.configure_hooks()
        with self.installation.replace_module(
            "hooks/runtime.py", "raise ImportError('broken')\n"
        ):
            result = self.scenario.doctor()
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertEqual(json.loads(result.stdout)["result"], "FAIL")

    def test_all_console_entries_and_interpreter(self) -> None:
        for name in (
            "codex-harness",
            "codex-harness-check",
            "codex-harness-ruff",
            "codex-harness-pre-tool",
            "codex-harness-post-tool",
        ):
            path = self.installation.scripts / name
            self.assertTrue(os.access(path, os.X_OK))
            self.assertIn(
                str(self.installation.scripts), path.read_text().splitlines()[0]
            )
        result = subprocess.run(
            [str(self.installation.python), "-I", "-c", "import codex_harness"],
            cwd=self.scenario.root,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_metrics_equal_decreasing_and_increasing(self) -> None:
        def source(count: int) -> str:
            return (
                "def lengthy():\n"
                + "".join(f"    value = {index}\n" for index in range(count))
                + "    return value\n"
            )

        self.scenario.file.write_text(source(85), encoding="utf-8")
        for name, count, expected in [
            ("equal", 85, "PASS"),
            ("less", 84, "PASS"),
            ("more", 86, "CHECK_FAILED"),
        ]:
            self.scenario.next_operation(name)
            self.prepare()
            self.scenario.file.write_text(
                source(count) + f"\nmarker = {count}\n", encoding="utf-8"
            )
            self.assert_result(
                self.scenario.invoke("post"), expected, expected == "CHECK_FAILED"
            )

    def test_syntax_regression_and_repair(self) -> None:
        self.prepare()
        self.scenario.file.write_text("def broken(:\n", encoding="utf-8")
        self.assert_result(self.scenario.invoke("post"), "CHECK_FAILED", True)
        self.scenario.next_operation("repair")
        self.prepare()
        self.scenario.file.write_text("value = 1\n", encoding="utf-8")
        self.assert_result(self.scenario.invoke("post"), "PASS")
        self.assertEqual(self.scenario.state()["consecutive_failed_attempts"], 0)

    def test_legacy_retry_state_and_corruption(self) -> None:
        self.prepare()
        self.scenario.state_path().write_text(
            json.dumps(
                {"consecutive_failed_attempts": 2, "last_failure": "old failure"}
            ),
            encoding="utf-8",
        )
        self.scenario.next_operation("legacy")
        self.prepare()
        self.assertEqual(self.scenario.state()["consecutive_failed_attempts"], 2)
        self.assertEqual(self.scenario.state()["last_failure"], "old failure")
        self.scenario.state_path().write_text("[]", encoding="utf-8")
        self.assert_result(self.scenario.invoke("post"), "HARNESS_ERROR", True)

    def test_interrupted_claim_and_snapshot_content(self) -> None:
        self.prepare()
        path = self.scenario.snapshot()
        raw = json.loads(path.read_text())
        raw["files"][str(self.scenario.file)]["content"] = "different baseline\n"
        path.write_text(json.dumps(raw), encoding="utf-8")
        self.assert_result(self.scenario.invoke("post"), "HARNESS_ERROR", True)
        self.scenario.next_operation("interrupted")
        self.prepare()
        path = self.scenario.snapshot()
        path.rename(path.with_suffix(".processing"))
        self.assert_result(self.scenario.invoke("post"), "HARNESS_ERROR", True)
        self.assertTrue(path.with_suffix(".processing").exists())

    def test_request_identity_collision(self) -> None:
        self.prepare()
        self.scenario.event["tool_input"]["command"] += "\n"
        self.assert_result(self.scenario.invoke("pre"), "HARNESS_ERROR", True)
        self.assert_result(self.scenario.invoke("post"), "HARNESS_ERROR", True)

    def test_doctor_inline_duplicate_and_matcher(self) -> None:
        path = self.scenario.configure_hooks()
        path.unlink()
        config = path.with_name("config.toml")
        text = ""
        for event, suffix in [("PreToolUse", "pre"), ("PostToolUse", "post")]:
            executable = self.installation.scripts / f"codex-harness-{suffix}-tool"
            text += f'[[hooks.{event}]]\nmatcher = "^apply_patch$"\n[[hooks.{event}.hooks]]\ntype = "command"\ncommand = "{executable}"\n'
        config.write_text(text, encoding="utf-8")
        self.assertEqual(self.scenario.doctor().returncode, 2)
        self.scenario.configure_hooks()
        self.assertEqual(self.scenario.doctor().returncode, 1)
        config.unlink()
        raw = json.loads(path.read_text())
        raw["hooks"]["PreToolUse"][0]["matcher"] = "^Bash$"
        path.write_text(json.dumps(raw), encoding="utf-8")
        self.assertEqual(self.scenario.doctor().returncode, 1)

    def test_stdin_read_error_and_stdout_failure(self) -> None:
        for name in ("pre", "post"):
            executable = self.installation.scripts / f"codex-harness-{name}-tool"
            module = f"hooks/{name}_tool.py"
            source = (
                (self.installation.package / module)
                .read_text()
                .replace(
                    "        event = json.load(sys.stdin)",
                    "        sys.stdin.close()\n        event = json.load(sys.stdin)",
                )
            )
            with self.installation.replace_module(module, source):
                self.assert_result(self.scenario.invoke(name), "HARNESS_ERROR", True)
            with open("/dev/full", "w", encoding="utf-8") as output:
                result = subprocess.run(
                    [str(executable)],
                    input="{",
                    stdout=output,
                    stderr=subprocess.PIPE,
                    text=True,
                    env=self.scenario.environment,
                    check=False,
                    timeout=30,
                )
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertIn("HARNESS_ERROR", result.stderr)
            with open("/dev/full", "w", encoding="utf-8") as output:
                result = subprocess.run(
                    [str(executable)],
                    input="{",
                    stdout=output,
                    stderr=output,
                    text=True,
                    env=self.scenario.environment,
                    check=False,
                    timeout=30,
                )
            self.assertEqual(result.returncode, 2)

    def test_interpreter_failure_is_not_harness_execution(self) -> None:
        executable = self.installation.scripts / "codex-harness-pre-tool"
        descriptor = os.open(self.scenario.root, os.O_RDONLY)
        try:
            result = subprocess.run(
                [str(executable)],
                stdin=descriptor,
                capture_output=True,
                text=True,
                env=self.scenario.environment,
                check=False,
                timeout=30,
            )
        finally:
            os.close(descriptor)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertIn("init_sys_streams", result.stderr)
        self.assertFalse((self.scenario.root / ".codex/harness/state").exists())

    def test_analyzer_runtime_failure_preserves_retry(self) -> None:
        self.introduce_regression()
        self.scenario.next_operation("analyzer-runtime")
        self.prepare()
        before = self.scenario.state()
        self.scenario.file.write_text("value = 9\n", encoding="utf-8")
        path = self.installation.package / "checks/analyzers/orchestrator.py"
        source = path.read_text().replace(
            "        if not documents:",
            '        raise RuntimeError("injected analyzer failure")\n        if not documents:',
        )
        with self.installation.replace_module(
            "checks/analyzers/orchestrator.py", source
        ):
            self.assert_result(self.scenario.invoke("post"), "HARNESS_ERROR", True)
        after = self.scenario.state()
        self.assertEqual(
            after["consecutive_failed_attempts"], before["consecutive_failed_attempts"]
        )
        self.assertEqual(after["last_failure"], before["last_failure"])

    def test_regression_policy_contract_in_installed_package(self) -> None:
        source = """
from dataclasses import replace
from codex_harness.checks.regression import DefaultRegressionPolicy
from codex_harness.checks.analyzers.schema import ToolFinding
policy = DefaultRegressionPolicy()
finding = ToolFinding('ruff', 'F401', 'unused', '/a.py', 1)
assert not policy.compare([finding], [replace(finding, line=5)])
assert len(policy.compare([finding], [finding, finding])) == 1
assert policy.compare([finding], [replace(finding, path='/b.py')])
assert policy.compare([finding], [replace(finding, tool='mypy')])
metric = ToolFinding('ruff', 'C901', 'complex', '/a.py', 1,
    comparison='metric', symbol='C.f', value=15, limit=10)
assert not policy.compare([metric], [metric])
assert not policy.compare([metric], [replace(metric, value=14)])
assert policy.compare([metric], [replace(metric, value=16)])
assert policy.compare([], [metric])
"""
        self.installation.command([str(self.installation.python), "-I", "-c", source])

    def test_non_applicable_tools_disabled_checks_and_scope(self) -> None:
        self.scenario.event["tool_name"] = "Bash"
        self.assert_result(self.scenario.invoke("pre"), "NOT_APPLICABLE")
        self.assert_result(self.scenario.invoke("post"), "NOT_APPLICABLE")
        self.scenario.event["tool_name"] = "apply_patch"
        self.scenario.event["agent_id"] = "agent"
        self.assert_result(self.scenario.invoke("pre"), "HARNESS_ERROR", True)
        del self.scenario.event["agent_id"]
        config = self.scenario.root / ".codex/harness/config/quality.toml"
        config.write_text(
            config.read_text().replace("enabled = true", "enabled = false"),
            encoding="utf-8",
        )
        self.assert_result(self.scenario.invoke("pre"), "NOT_APPLICABLE")
        self.scenario.file.write_text("bad syntax !\n", encoding="utf-8")
        self.assert_result(self.scenario.invoke("post"), "NOT_APPLICABLE")

    def test_doctor_quality_config_and_missing_handlers(self) -> None:
        self.assertEqual(self.scenario.doctor().returncode, 1)
        self.scenario.configure_hooks()
        config = self.scenario.root / ".codex/harness/config/quality.toml"
        config.parent.mkdir(parents=True, exist_ok=True)
        config.write_text("broken = [", encoding="utf-8")
        result = self.scenario.doctor()
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertEqual(config.read_text(), "broken = [")

    def test_foreign_and_incomplete_receipts_never_pass(self) -> None:
        self.prepare()
        self.scenario.file.write_text("value = 2\n", encoding="utf-8")
        self.assert_result(self.scenario.invoke("post"), "PASS")
        original = self.scenario.state_path().read_text()
        for key, value in [("scope", "other"), ("files", {}), ("completed", False)]:
            with self.subTest(key=key):
                raw = json.loads(original)
                record = next(iter(raw["operations"].values()))
                record[key] = value
                self.scenario.state_path().write_text(json.dumps(raw), encoding="utf-8")
                self.assert_result(self.scenario.invoke("post"), "HARNESS_ERROR", True)
        self.scenario.state_path().write_text(original, encoding="utf-8")
        self.scenario.next_operation("different-operation")
        self.assert_result(self.scenario.invoke("post"), "HARNESS_ERROR", True)
