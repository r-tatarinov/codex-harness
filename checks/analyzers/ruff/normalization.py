"""Map Ruff metric diagnostics to symbols and numeric findings."""

import ast
import re
from collections.abc import Iterable

from ...finding import Finding
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
) -> Finding:
    if diagnostic.code not in limits or not isinstance(diagnostic.message, str):
        raise RuntimeError(f"Unexpected Ruff metric diagnostic: {diagnostic.code}")
    measurement = MEASUREMENT_RE.search(diagnostic.message)
    if measurement is None:
        raise RuntimeError(f"Unrecognized Ruff metric message: {diagnostic.message}")
    value, limit = map(int, measurement.groups())
    if limit != limits[diagnostic.code] or value <= limit:
        raise RuntimeError(f"Invalid Ruff metric measurement: {diagnostic.message}")
    return Finding(
        rule=diagnostic.code,
        path=diagnostic.path,
        symbol=symbol,
        line=diagnostic.line,
        value=value,
        message=f"{diagnostic.code} {symbol}: {diagnostic.message}",
    )


def collapse_nesting(findings: Iterable[Finding]) -> list[Finding]:
    others: list[Finding] = []
    nesting: dict[str, Finding] = {}
    for finding in findings:
        if finding.rule != "PLR1702":
            others.append(finding)
            continue
        previous = nesting.get(finding.symbol)
        if previous is None or (finding.value, -finding.line) > (
            previous.value,
            -previous.line,
        ):
            nesting[finding.symbol] = finding
    others.extend(sorted(nesting.values(), key=lambda item: item.line))
    return others
