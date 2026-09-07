import ast
from pathlib import Path

from finding import Finding

NESTING_NODES = (
    ast.If,
    ast.For,
    ast.AsyncFor,
    ast.While,
    ast.Try,
    ast.With,
    ast.AsyncWith,
    ast.Match,
)


def is_nested_scope(node: ast.AST) -> bool:
    return isinstance(
        node,
        (
            ast.FunctionDef,
            ast.AsyncFunctionDef,
            ast.ClassDef,
        ),
    )


def is_elif(parent: ast.AST, child: ast.AST) -> bool:
    return (
        isinstance(parent, ast.If)
        and isinstance(child, ast.If)
        and child in parent.orelse
    )


def get_max_depth(
    node: ast.AST,
    depth: int = 0,
) -> int:
    max_depth = depth

    for child in ast.iter_child_nodes(node):
        if is_nested_scope(child):
            continue

        child_depth = depth

        if isinstance(child, NESTING_NODES) and not is_elif(node, child):
            child_depth += 1

        max_depth = max(
            max_depth,
            get_max_depth(
                child,
                child_depth,
            ),
        )

    return max_depth


def check(
    tree: ast.AST,
    path: Path,
    max_nesting: int,
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

        depth = get_max_depth(node)

        if depth <= max_nesting:
            continue

        symbol = symbols.get(
            id(node),
            node.name,
        )

        findings.append(
            Finding(
                rule="nesting",
                path=str(path),
                symbol=symbol,
                line=node.lineno,
                value=depth,
                limit=max_nesting,
                message=(f"{symbol} has nesting depth {depth} (maximum {max_nesting})"),
            )
        )

    return findings
