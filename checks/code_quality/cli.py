"""Command-line output and exit handling for the quality checker."""

import sys
from pathlib import Path

from finding import Finding

from .config import load_config
from .service import analyze_file


def print_findings(findings: list[Finding]) -> None:
    print("CODE QUALITY CHECK FAILED")

    for finding in findings:
        print(f"- {finding.path}:{finding.line}: {finding.message}")


def main() -> int:
    config = load_config()

    findings: list[Finding] = []

    for path in map(Path, sys.argv[1:]):
        if path.suffix != ".py" or not path.is_file():
            continue

        try:
            findings.extend(
                analyze_file(
                    path=path,
                    config=config,
                )
            )
        except (
            OSError,
            SyntaxError,
            TypeError,
            ValueError,
            KeyError,
            RuntimeError,
        ) as exc:
            print(
                f"{path}: cannot analyze file: {exc}",
                file=sys.stderr,
            )
            return 1

    if not findings:
        return 0

    print_findings(findings)

    return 1
