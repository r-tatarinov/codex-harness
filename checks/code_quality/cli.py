import sys
from pathlib import Path

from ..analyzers.orchestrator import AnalyzerOrchestrator
from ..analyzers.registry import BUILTIN_ANALYZERS
from ..analyzers.schema import ToolFinding
from ..config import CONFIG_PATH
from ..config.loader import ConfigurationLoader


def format_findings(findings: list[ToolFinding]) -> str:
    lines = ["CODE QUALITY CHECK FAILED"]
    lines.extend(
        f"- {finding.path}:{finding.line}:{finding.column}: "
        f"[{finding.tool}] {finding.code} {finding.message}"
        for finding in findings
    )
    return "\n".join(lines)


def main() -> int:
    paths = list(map(Path, sys.argv[1:]))
    try:
        orchestrator = AnalyzerOrchestrator(
            ConfigurationLoader(CONFIG_PATH).load(),
            (cls() for cls in BUILTIN_ANALYZERS),
        )
        findings = orchestrator.analyze_files(paths)
    except (OSError, SyntaxError, TypeError, ValueError, KeyError, RuntimeError) as exc:
        print(f"cannot analyze files: {exc}", file=sys.stderr)
        return 1

    if not findings:
        return 0

    print(format_findings(findings))

    return 1
