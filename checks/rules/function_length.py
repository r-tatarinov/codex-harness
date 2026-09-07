import ast
from pathlib import Path

from finding import Finding


def check(
    tree: ast.AST,
    path: Path,
    max_lines: int,
    symbols: dict[int, str],
) -> list[Finding]:
    findings: list[Finding] = []

    for node in ast.walk(tree):
        if not isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
            ),
        ):
            continue

        if node.end_lineno is None:
            continue

        lines = node.end_lineno - node.lineno + 1

        if lines <= max_lines:
            continue

        symbol = symbols.get(
            id(node),
            node.name,
        )

        findings.append(
            Finding(
                rule="function_length",
                path=str(path),
                symbol=symbol,
                line=node.lineno,
                value=lines,
                limit=max_lines,
                message=(f"{symbol} has {lines} lines (maximum {max_lines})"),
            )
        )

    return findings
