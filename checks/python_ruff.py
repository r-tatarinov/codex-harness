#!/usr/bin/env python3

import subprocess
import sys
from pathlib import Path


RUFF = Path.home() / ".local" / "bin" / "ruff"


def main() -> int:
    files = [
        Path(path)
        for path in sys.argv[1:]
        if Path(path).suffix == ".py"
    ]

    if not files:
        return 0

    result = subprocess.run(
        [
            str(RUFF),
            "check",
            *map(str, files),
        ],
    )

    return result.returncode


if __name__ == "__main__":
    sys.exit(main())

