"""Execute Ruff with the selected options and read source files."""

import subprocess
import sys
from pathlib import Path

from .parsing import parse_output
from .schema import RuffFinding

RUFF_COMMAND = (sys.executable, "-m", "ruff")


def run_check(
    source: str,
    path: Path,
    options: tuple[str, ...] = (),
) -> list[RuffFinding]:
    path = path.resolve()
    result = subprocess.run(
        [
            *RUFF_COMMAND,
            "check",
            *options,
            "--output-format",
            "json",
            "--stdin-filename",
            str(path),
            "-",
        ],
        input=source,
        text=True,
        capture_output=True,
        cwd=path.parent,
        check=False,
        timeout=10,
    )

    if result.returncode not in (0, 1):
        raise RuntimeError(
            result.stderr.strip() or f"Ruff failed with exit code {result.returncode}"
        )

    return parse_output(result.stdout, result.returncode, path)


analyze_source = run_check


def analyze_file(path: Path) -> list[RuffFinding]:
    source = path.read_text(encoding="utf-8")

    return analyze_source(
        source=source,
        path=path,
    )
