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
    timeout: int = 10,
    cwd: Path | None = None,
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
        cwd=cwd or path.parent,
        check=False,
        timeout=timeout,
    )
    if result.returncode not in (0, 1):
        raise RuntimeError(
            result.stderr.strip() or f"Ruff failed with exit code {result.returncode}"
        )
    return parse_output(result.stdout, result.returncode, path)
