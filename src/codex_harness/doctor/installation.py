import importlib.metadata
import os
import subprocess
import sys
import sysconfig
import tempfile
from pathlib import Path

from .schema import Check, Installation


class InstallationInspector:
    def inspect(self) -> tuple[Installation, list[Check]]:
        distribution = importlib.metadata.distribution("codex-harness")
        scripts = Path(sysconfig.get_path("scripts"))
        installation = Installation(
            Path(sys.executable),
            scripts / "codex-harness-pre-tool",
            scripts / "codex-harness-post-tool",
            distribution.version,
        )
        expected = {
            "codex-harness": "codex_harness.cli:main",
            "codex-harness-check": "codex_harness.checks.code_quality:main",
            "codex-harness-ruff": "codex_harness.checks.analyzers.ruff.cli:main",
            "codex-harness-pre-tool": "codex_harness.hooks.pre_tool:main",
            "codex-harness-post-tool": "codex_harness.hooks.post_tool:main",
        }
        actual = {item.name: item.value for item in distribution.entry_points}
        errors = [
            name
            for name, target in expected.items()
            if actual.get(name) != target or not os.access(scripts / name, os.X_OK)
        ]
        for path in (installation.pre, installation.post):
            if path.is_file():
                first_line = path.read_text(encoding="utf-8").splitlines()[0]
                interpreter = Path(first_line.removeprefix("#!"))
                if interpreter.parent != scripts or not interpreter.is_file():
                    errors.append(
                        f"{path.name}: interpreter does not match this environment"
                    )
        checks = [
            Check(
                "Entry points",
                "FAIL" if errors else "PASS",
                (
                    "Missing or incorrect: " + ", ".join(errors)
                    if errors
                    else str(scripts)
                ),
            )
        ]
        with tempfile.TemporaryDirectory(prefix="harness-import-") as directory:
            result = subprocess.run(
                [
                    sys.executable,
                    "-I",
                    "-c",
                    (
                        "import black, flake8, mypy, pylint, ruff; "
                        "import codex_harness.hooks.runtime; "
                        "import codex_harness.doctor.service; "
                        "from codex_harness.checks.config.defaults import DEFAULT_CONFIG; "
                        "assert DEFAULT_CONFIG.is_file()"
                    ),
                ],
                cwd=directory,
                check=False,
                capture_output=True,
                text=True,
                timeout=30,
            )
        checks.append(
            Check(
                "Package",
                "PASS" if result.returncode == 0 else "FAIL",
                (
                    f"{distribution.version}, interpreter {sys.executable}"
                    if result.returncode == 0
                    else "Installed modules/defaults cannot be imported; reinstall this wheel and dependencies"
                ),
            )
        )
        return installation, checks
