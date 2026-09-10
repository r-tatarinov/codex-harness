"""Parse source and run the global numeric quality adapters."""

import ast
from pathlib import Path

from ..finding import Finding
from ..function_length import check as check_function_length
from ..ruff_metrics import check as check_ruff_metrics
from ..symbols import build_symbol_index
from .config import load_max_function_lines


class SourceSyntaxError(ValueError):
    """The Python source being checked could not be parsed."""


def parse_source(source: str, path: Path) -> ast.Module:
    try:
        return ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        raise SourceSyntaxError(
            f"{exc.filename}:{exc.lineno}:{exc.offset}: SyntaxError: {exc.msg}"
        ) from exc


def analyze_source(
    source: str,
    path: Path,
) -> list[Finding]:
    tree = parse_source(source, path)

    symbols = build_symbol_index(tree)

    findings = check_function_length(
        source=source,
        tree=tree,
        path=path,
        max_lines=load_max_function_lines(),
        symbols=symbols,
    )
    findings.extend(
        check_ruff_metrics(
            source=source,
            tree=tree,
            path=path,
            symbols=symbols,
        )
    )
    return findings


def analyze_file(
    path: Path,
) -> list[Finding]:
    source = path.read_text(encoding="utf-8")

    return analyze_source(
        source=source,
        path=path,
    )
