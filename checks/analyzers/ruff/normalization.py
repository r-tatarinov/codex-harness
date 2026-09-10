import ast
import re
from collections.abc import Iterable

from ..schema import ToolFinding
from .schema import RuffFinding

MEASUREMENT_RE = re.compile(r"\((\d+) > (\d+)\)$")


def find_symbol(
    diagnostic: RuffFinding,
    functions: list[ast.FunctionDef | ast.AsyncFunctionDef],
    symbols: dict[int, str],
) -> str:
    for node in functions:
        if diagnostic.line == node.lineno:
            return symbols[id(node)]
        if (
            diagnostic.code == "PLR1702"
            and node.end_lineno is not None
            and node.lineno < diagnostic.line <= node.end_lineno
        ):
            return symbols[id(node)]
    raise RuntimeError(f"Cannot locate function for Ruff metric: {diagnostic}")


def to_finding(
    diagnostic: RuffFinding,
    limits: dict[str, int],
    symbol: str,
) -> ToolFinding:
    if diagnostic.code not in limits or not isinstance(diagnostic.message, str):
        raise RuntimeError(f"Unexpected Ruff metric diagnostic: {diagnostic.code}")
    measurement = MEASUREMENT_RE.search(diagnostic.message)
    if measurement is None:
        raise RuntimeError(f"Unrecognized Ruff metric message: {diagnostic.message}")
    value, limit = map(int, measurement.groups())
    if limit != limits[diagnostic.code] or value <= limit:
        raise RuntimeError(f"Invalid Ruff metric measurement: {diagnostic.message}")
    return ToolFinding(
        tool="ruff",
        comparison="metric",
        limit=limit,
        code=diagnostic.code,
        path=diagnostic.path,
        symbol=symbol,
        line=diagnostic.line,
        value=value,
        message=diagnostic.message,
    )


def collapse_nesting(findings: Iterable[ToolFinding]) -> list[ToolFinding]:
    others: list[ToolFinding] = []
    nesting: dict[tuple[str, str | None], ToolFinding] = {}
    for finding in findings:
        if finding.code != "PLR1702":
            others.append(finding)
            continue
        assert finding.value is not None
        previous = nesting.get((finding.path, finding.symbol))
        if (
            previous is None
            or previous.value is None
            or (finding.value, -finding.line)
            > (
                previous.value,
                -previous.line,
            )
        ):
            nesting[finding.path, finding.symbol] = finding
    others.extend(sorted(nesting.values(), key=lambda item: item.line))
    return others


def ordinary_finding(item: RuffFinding) -> ToolFinding:
    return ToolFinding(
        tool="ruff",
        code=item.code,
        message=item.message,
        path=item.path,
        line=item.line,
        column=item.column,
    )
