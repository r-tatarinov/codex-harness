import sys
from pathlib import Path

from .runner import run_check
from .schema import RuffFinding


def format_findings(findings: list[RuffFinding]) -> str:
    return "\n".join(
        f"{finding.path}:{finding.line}:{finding.column}: "
        f"{finding.code} {finding.message}"
        for finding in findings
    )


def main() -> int:
    findings: list[RuffFinding] = []
    for path in map(Path, sys.argv[1:]):
        if path.suffix == ".py" and path.is_file():
            findings.extend(run_check(path.read_text(encoding="utf-8"), path))
    if not findings:
        return 0
    print(format_findings(findings))
    return 1
