#!/usr/bin/env python3

import json
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path


RUFF = Path.home() / ".local" / "bin" / "ruff"


@dataclass(frozen=True)
class RuffFinding:
    code: str
    message: str
    path: str
    line: int
    column: int

    @property
    def key(self) -> tuple[str, str]:
        return self.code, self.message


def analyze_source(
    source: str,
    path: Path,
) -> list[RuffFinding]:
    result = subprocess.run(
        [
            str(RUFF),
            "check",
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
    )

    if result.returncode not in (0, 1):
        raise RuntimeError(
            result.stderr.strip()
            or f"Ruff failed with exit code {result.returncode}"
        )

    if not result.stdout.strip():
        return []

    diagnostics = json.loads(result.stdout)

    findings: list[RuffFinding] = []

    for diagnostic in diagnostics:
        location = diagnostic["location"]

        findings.append(
            RuffFinding(
                code=diagnostic["code"],
                message=diagnostic["message"],
                path=str(path),
                line=location["row"],
                column=location["column"],
            )
        )

    return findings


def analyze_file(path: Path) -> list[RuffFinding]:
    source = path.read_text(encoding="utf-8")

    return analyze_source(
        source=source,
        path=path,
    )


def find_regressions(
    before: list[RuffFinding],
    after: list[RuffFinding],
) -> list[RuffFinding]:
    before_counts = Counter(
        finding.key
        for finding in before
    )

    regressions: list[RuffFinding] = []

    for finding in after:
        if before_counts[finding.key] > 0:
            before_counts[finding.key] -= 1
            continue

        regressions.append(finding)

    return regressions


def print_findings(
    findings: list[RuffFinding],
) -> None:
    for finding in findings:
        print(
            f"{finding.path}:{finding.line}:{finding.column}: "
            f"{finding.code} {finding.message}"
        )


def main() -> int:
    python_files = [
        Path(argument)
        for argument in sys.argv[1:]
        if Path(argument).suffix == ".py"
    ]

    findings: list[RuffFinding] = []

    for path in python_files:
        if not path.is_file():
            continue

        findings.extend(
            analyze_file(path)
        )

    if not findings:
        return 0

    print_findings(findings)

    return 1


if __name__ == "__main__":
    sys.exit(main())

