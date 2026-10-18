import json
import os
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


class WheelInstallation:
    def __init__(self, root: Path, repository: Path) -> None:
        self.root = root
        self.repository = repository
        self.python = root / "venv/bin/python"
        self.scripts = self.python.parent
        self.package = root / "venv/lib/python3.12/site-packages/codex_harness"

    def build(self) -> None:
        source = self.root / "source"
        shutil.copytree(
            self.repository,
            source,
            ignore=shutil.ignore_patterns(
                ".git",
                ".venv",
                "venv",
                "state",
                "build",
                "dist",
                "*.egg-info",
                "__pycache__",
                ".mypy_cache",
                ".ruff_cache",
            ),
        )
        self.command(
            [
                sys.executable,
                "-m",
                "build",
                "--wheel",
                "--no-isolation",
                "--outdir",
                str(self.root / "dist"),
                str(source),
            ]
        )
        self.command([sys.executable, "-m", "venv", str(self.root / "venv")])
        wheel = next((self.root / "dist").glob("*.whl"))
        self.command(
            [
                str(self.python),
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                str(wheel),
            ]
        )
        result = self.command(
            [
                str(self.python),
                "-I",
                "-c",
                "import codex_harness; print(codex_harness.__path__[0])",
            ]
        )
        self.package = Path(result.stdout.strip())
        shutil.rmtree(source)

    def command(self, arguments: list[str]) -> subprocess.CompletedProcess[str]:
        environment = dict(os.environ, PIP_CACHE_DIR=str(self.root / "pip-cache"))
        return subprocess.run(
            arguments,
            env=environment,
            cwd=self.root,
            capture_output=True,
            text=True,
            check=True,
            timeout=180,
        )

    @contextmanager
    def replace_module(self, name: str, source: str) -> Iterator[None]:
        path = self.package / name
        original = path.read_bytes()
        path.write_text(source, encoding="utf-8")
        shutil.rmtree(path.parent / "__pycache__", ignore_errors=True)
        try:
            yield
        finally:
            path.write_bytes(original)
            shutil.rmtree(path.parent / "__pycache__", ignore_errors=True)


class HookScenario:
    def __init__(self, installation: WheelInstallation) -> None:
        self.installation = installation
        self.directory = tempfile.TemporaryDirectory(prefix="harness-case-")
        self.root = Path(self.directory.name)
        self.project = self.root / "project"
        self.project.mkdir()
        self.file = self.project / "sample.py"
        self.file.write_text("value = 1\n", encoding="utf-8")
        self.environment = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith("PYTHON")
        }
        self.environment.update(
            HOME=str(self.root), CODEX_HOME=str(self.root / ".codex")
        )
        self.event = {
            "session_id": "session",
            "turn_id": "turn",
            "tool_use_id": "operation",
            "cwd": str(self.project),
            "tool_name": "apply_patch",
            "tool_input": {
                "command": "*** Begin Patch\n*** Update File: sample.py\n@@\n-value = 1\n+value = 2\n*** End Patch"
            },
        }

    def invoke(
        self, name: str, value: object = None, *, closed_input: bool = False
    ) -> subprocess.CompletedProcess[str]:
        event_name = "PreToolUse" if name == "pre" else "PostToolUse"
        payload = (
            json.dumps({**self.event, "hook_event_name": event_name})
            if value is None
            else str(value)
        )
        executable = self.installation.scripts / f"codex-harness-{name}-tool"
        if closed_input:
            return subprocess.run(
                [str(executable)],
                stdin=subprocess.DEVNULL,
                text=True,
                capture_output=True,
                env=self.environment,
                cwd=self.root,
                check=False,
                timeout=60,
            )
        return subprocess.run(
            [str(executable)],
            input=payload,
            text=True,
            capture_output=True,
            env=self.environment,
            cwd=self.root,
            check=False,
            timeout=60,
        )

    def state_path(self) -> Path:
        return next((self.root / ".codex/harness/state").rglob("attempts.json"))

    def state(self) -> dict:
        return json.loads(self.state_path().read_text())

    def snapshot(self) -> Path:
        return next((self.root / ".codex/harness/state").rglob("patch-*.json"))

    def next_operation(self, name: str) -> None:
        self.event["tool_use_id"] = name

    def configure_hooks(
        self, *, legacy: bool = False, asynchronous: bool = False
    ) -> Path:
        target = self.root / ".codex/hooks.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        hooks = {}
        for event, name in [("PreToolUse", "pre"), ("PostToolUse", "post")]:
            command = (
                f"python3 /old/codex_harness/hooks/{name}_tool.py"
                if legacy
                else str(self.installation.scripts / f"codex-harness-{name}-tool")
            )
            hooks[event] = [
                {
                    "matcher": "^apply_patch$",
                    "hooks": [
                        {"type": "command", "command": command, "async": asynchronous}
                    ],
                }
            ]
        target.write_text(json.dumps({"hooks": hooks}), encoding="utf-8")
        return target

    def doctor(self) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                str(self.installation.scripts / "codex-harness"),
                "doctor",
                "--json",
                "--cwd",
                str(self.project),
            ],
            cwd=self.root,
            env=self.environment,
            capture_output=True,
            text=True,
            check=False,
            timeout=180,
        )
