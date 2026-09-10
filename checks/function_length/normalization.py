"""Normalize CFQ001 without calculating function length inside Harness."""

import ast
import re

from ..finding import Finding
from ..python_flake8 import Flake8Finding

MEASUREMENT_RE = re.compile(
    r"^Function (?P<name>\S+) has length (?P<value>\d+) "
    r"that exceeds max allowed length (?P<limit>\d+)$"
)


def find_symbol(
    diagnostic: Flake8Finding,
    functions: list[ast.FunctionDef | ast.AsyncFunctionDef],
    symbols: dict[int, str],
) -> str:
    for node in functions:
        if diagnostic.line == node.lineno:
            return symbols[id(node)]
    raise RuntimeError(f"Cannot locate function for CFQ001: {diagnostic}")


def to_finding(
    diagnostic: Flake8Finding,
    max_lines: int,
    symbol: str,
) -> Finding:
    measurement = MEASUREMENT_RE.fullmatch(diagnostic.message)
    if measurement is None:
        raise RuntimeError(f"Unrecognized CFQ001 message: {diagnostic.message}")
    value = int(measurement.group("value"))
    reported_limit = int(measurement.group("limit"))
    if measurement.group("name") != symbol.rsplit(".", maxsplit=1)[-1]:
        raise RuntimeError(f"CFQ001 function name does not match {symbol}")
    if reported_limit != max_lines or value <= max_lines:
        raise RuntimeError(f"Invalid CFQ001 measurement: {diagnostic.message}")
    return Finding(
        rule="CFQ001",
        path=diagnostic.path,
        symbol=symbol,
        line=diagnostic.line,
        value=value,
        message=f"CFQ001 {symbol}: {diagnostic.message}",
    )
