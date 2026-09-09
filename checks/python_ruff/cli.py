"""Command-line output and exit handling for Ruff diagnostics."""

import sys
from pathlib import Path

from .runner import analyze_file
from .schema import RuffFinding


def print_findings(
    findings: list[RuffFinding],
) -> None:
    for finding in findings:
        print(
            f"{finding.path}:{finding.line}:{finding.column}: "
            f"{finding.code} {finding.message}"
        )


def main() -> int:
    findings: list[RuffFinding] = []

    for path in map(Path, sys.argv[1:]):
        if path.suffix != ".py" or not path.is_file():
            continue

        findings.extend(analyze_file(path))

    if not findings:
        return 0

    print_findings(findings)

    return 1
