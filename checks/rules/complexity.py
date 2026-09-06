import ast
from pathlib import Path

from radon.complexity import cc_visit_ast
from radon.visitors import Function

from finding import Finding


def get_symbol(block: Function) -> str:
    if block.is_method and block.classname:
        return f"{block.classname}.{block.name}"

    return block.name


def check(
    tree: ast.AST,
    path: Path,
    max_complexity: int,
    symbols: dict[int, str],
) -> list[Finding]:
    findings: list[Finding] = []

    for block in cc_visit_ast(tree):
        if not isinstance(block, Function):
            continue

        if block.complexity <= max_complexity:
            continue

        symbol = get_symbol(block)

        findings.append(
            Finding(
                rule="complexity",
                path=str(path),
                symbol=symbol,
                line=block.lineno,
                value=block.complexity,
                limit=max_complexity,
                message=(
                    f"{symbol} has complexity {block.complexity} "
                    f"(maximum {max_complexity})"
                ),
            )
        )

    return findings

