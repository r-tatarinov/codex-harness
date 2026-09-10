"""Run the mandatory flake8-functions pass against source from stdin."""

import subprocess
import sys
from pathlib import Path

from .parsing import DELIMITER, parse_output
from .schema import Flake8Finding

FLAKE8_COMMAND = (sys.executable, "-m", "flake8")
OUTPUT_FORMAT = DELIMITER.join(("%(row)d", "%(col)d", "%(code)s", "%(text)s"))


def run_check(source: str, path: Path, max_lines: int) -> list[Flake8Finding]:
    path = path.resolve()
    result = subprocess.run(
        [
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
            result.stderr.strip() or f"Flake8 failed with exit code {result.returncode}"
        )
    if result.stderr.strip():
        raise RuntimeError(
            f"Flake8 returned unexpected stderr: {result.stderr.strip()}"
        )
    return parse_output(result.stdout, result.returncode, path)
