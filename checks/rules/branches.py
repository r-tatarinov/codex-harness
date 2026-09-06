import ast
from pathlib import Path

from finding import Finding


FUNCTION_NODES = (
    ast.FunctionDef,
    ast.AsyncFunctionDef,
    ast.Lambda,
    ast.ClassDef,
)


def count_node_branches(node: ast.AST) -> int:
    if isinstance(node, ast.If):
        return 1

    if isinstance(
        node,
        (
            ast.For,
            ast.AsyncFor,
            ast.While,
        ),
    ):
        return 1

    if isinstance(node, ast.Try):
        branches = len(node.handlers)

        if node.orelse:
            branches += 1

        return branches

    if isinstance(node, ast.Match):
        return len(node.cases)

    return 0


def count_branches(node: ast.AST) -> int:
    branches = 0

    for child in ast.iter_child_nodes(node):
        if isinstance(child, FUNCTION_NODES):
            continue

        branches += count_node_branches(child)
        branches += count_branches(child)

    return branches


def check(
    tree: ast.AST,
    path: Path,
    max_branches: int,
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

        branches = count_branches(node)

        if branches <= max_branches:
            continue

        symbol = symbols.get(
            id(node),
            node.name,
        )

        findings.append(
            Finding(
                rule="branches",
                path=str(path),
                symbol=symbol,
                line=node.lineno,
                value=branches,
                limit=max_branches,
                message=(
                    f"{symbol} has {branches} branches "
                    f"(maximum {max_branches})"
                ),
            )
        )

    return findings

