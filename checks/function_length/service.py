"""Run flake8-functions and turn CFQ001 diagnostics into numeric findings."""

import ast
from pathlib import Path

from ..finding import Finding
from ..python_flake8 import run_check
from .normalization import find_symbol, to_finding


def check(
    source: str,
    tree: ast.AST,
    path: Path,
    max_lines: int,
    symbols: dict[int, str],
) -> list[Finding]:
    functions = [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    diagnostics = run_check(source, path, max_lines)
    return [
        to_finding(item, max_lines, find_symbol(item, functions, symbols))
        for item in diagnostics
    ]
