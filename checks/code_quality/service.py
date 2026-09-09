"""Parse source and run the custom length rule and Ruff metric adapter."""

import ast
from pathlib import Path

from finding import Finding
from ruff_metrics import check as check_ruff_metrics
from rules.function_length import check as check_function_length
from symbols import build_symbol_index


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
    config: dict,
) -> list[Finding]:
    tree = parse_source(source, path)

    symbols = build_symbol_index(tree)
    function_config = config["python"]["functions"]

    findings = check_function_length(
        tree=tree,
        path=path,
        max_lines=function_config["max_lines"],
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
    config: dict,
) -> list[Finding]:
    source = path.read_text(encoding="utf-8")

    return analyze_source(
        source=source,
        path=path,
        config=config,
    )
