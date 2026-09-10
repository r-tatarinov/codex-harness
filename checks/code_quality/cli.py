"""Command-line output and exit handling for the quality checker."""

import sys
from pathlib import Path

from ..analyzers.orchestrator import analyze_files
from ..analyzers.schema import ToolFinding


def print_findings(findings: list[ToolFinding]) -> None:
    print("CODE QUALITY CHECK FAILED")

    for finding in findings:
        print(
            f"- {finding.path}:{finding.line}:{finding.column}: "
            f"[{finding.tool}] {finding.code} {finding.message}"
        )


def main() -> int:
    paths = list(map(Path, sys.argv[1:]))
    try:
        findings = analyze_files(paths)
    except (OSError, SyntaxError, TypeError, ValueError, KeyError, RuntimeError) as exc:
        print(f"cannot analyze files: {exc}", file=sys.stderr)
        return 1

    if not findings:
        return 0

    print_findings(findings)

    return 1
