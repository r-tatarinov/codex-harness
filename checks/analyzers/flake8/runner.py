import subprocess
import sys
from pathlib import Path

from ...config.schema import ToolConfig
from ..schema import SourceDocument, ToolFinding
from .parsing import OUTPUT_FORMAT, parse_metric_output, parse_regular_output
from .schema import Flake8Finding

FLAKE8_COMMAND = (sys.executable, "-m", "flake8")


def _execute(
    command: list[str], source: str, cwd: Path, timeout: int
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command,
        input=source,
        text=True,
        capture_output=True,
        cwd=cwd,
        check=False,
        timeout=timeout,
    )
    if result.returncode not in (0, 1):
        raise RuntimeError(
            result.stderr.strip() or f"Flake8 failed with exit code {result.returncode}"
        )
    if result.stderr.strip():
        raise RuntimeError(
            f"Flake8 returned unexpected stderr: {result.stderr.strip()}"
        )
    return result


def run_regular_check(
    document: SourceDocument, config: ToolConfig
) -> list[ToolFinding]:
    selected = tuple(
        code for code in config.rules.get("select", ()) if code != "CFQ001"
    )
    if not selected:
        return []
    command = [*FLAKE8_COMMAND]
    if not config.use_project_config:
        command.append("--isolated")
    if config.plugins:
        command.extend(("--require-plugins", ",".join(config.plugins)))
    command.extend(("--select", ",".join(selected)))
    ignored = config.rules.get("ignore", ())
    if ignored:
        command.extend(("--ignore", ",".join(ignored)))
    for name, value in config.options.items():
        command.extend((f"--{name.replace('_', '-')}", str(value)))
    path = document.path.resolve()
    command.extend(("--format", OUTPUT_FORMAT, "--stdin-display-name", str(path), "-"))
    result = _execute(
        command, document.source, document.working_directory, config.timeout_seconds
    )
    return parse_regular_output(result.stdout, result.returncode, path)


def run_metric_check(
    source: str,
    path: Path,
    max_lines: int,
    timeout: int = 10,
    cwd: Path | None = None,
) -> list[Flake8Finding]:
    path = path.resolve()
    command = [
        *FLAKE8_COMMAND,
        "--isolated",
        "--require-plugins",
        "flake8-functions",
        "--disable-noqa",
        "--select",
        "CFQ001",
        "--max-function-length",
        str(max_lines),
        "--format",
        OUTPUT_FORMAT,
        "--stdin-display-name",
        str(path),
        "-",
    ]
    result = _execute(command, source, cwd or path.parent, timeout)
    return parse_metric_output(result.stdout, result.returncode, path)
