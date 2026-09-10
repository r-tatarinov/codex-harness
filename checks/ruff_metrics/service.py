"""Run the metric pass and normalize its results for regression comparison."""

import ast
from pathlib import Path

from ..analyzers.ruff.configuration import metric_options
from ..analyzers.ruff.normalization import collapse_nesting, find_symbol, to_finding
from ..analyzers.ruff.runner import run_check
from ..finding import Finding
from .config import load_limits


def check(
    source: str,
    path: Path,
    tree: ast.AST,
    symbols: dict[int, str],
) -> list[Finding]:
    limits = load_limits()
    functions = [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    functions.sort(key=lambda node: (node.lineno, node.col_offset), reverse=True)
    diagnostics = run_check(source, path, metric_options(limits))
    findings = (
        to_finding(item, limits, find_symbol(item, functions, symbols))
        for item in diagnostics
    )
    return collapse_nesting(findings)
