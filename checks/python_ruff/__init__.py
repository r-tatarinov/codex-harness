"""Public API for Ruff execution and normalized diagnostics."""

from .cli import main, print_findings
from .parsing import parse_diagnostic
from .runner import RUFF, analyze_file, analyze_source, run_check
from .schema import RuffFinding

__all__ = [
    "RUFF",
    "RuffFinding",
    "analyze_file",
    "analyze_source",
    "main",
    "parse_diagnostic",
    "print_findings",
    "run_check",
]
