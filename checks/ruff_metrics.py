"""Global Harness metrics, measured by Ruff and compared numerically."""

import ast
import re
import tomllib
from pathlib import Path

from finding import Finding
from python_ruff import RuffFinding, run_check

CONFIG_PATH = Path(__file__).resolve().parents[1] / "pyproject.toml"
METRIC_SETTINGS = {
    "C901": ("mccabe", "max-complexity"),
    "PLR0912": ("pylint", "max-branches"),
}
METRIC_CODES = frozenset(METRIC_SETTINGS)
MEASUREMENT_RE = re.compile(r"\((\d+) > (\d+)\)$")


def load_limits() -> dict[str, int]:
    with CONFIG_PATH.open("rb") as file:
        lint = tomllib.load(file)["tool"]["ruff"]["lint"]

    limits = {}
    for code, (plugin, setting) in METRIC_SETTINGS.items():
        value = lint[plugin][setting]
        if type(value) is not int or value < 0:
            raise ValueError(f"Invalid Harness Ruff limit: {plugin}.{setting}")
        limits[code] = value
    return limits


def build_options(limits: dict[str, int]) -> tuple[str, ...]:
    options = [
        "--isolated",
        "--ignore-noqa",
        "--select",
        ",".join(METRIC_SETTINGS),
    ]
    for code, (plugin, setting) in METRIC_SETTINGS.items():
        options.extend(("--config", f"lint.{plugin}.{setting}={limits[code]}"))
    return tuple(options)


def to_finding(
    diagnostic: RuffFinding,
    limits: dict[str, int],
    symbols_by_line: dict[int, str],
) -> Finding:
    # Ruff JSON currently exposes the measurement only in the message. Reject
    # unexpected formats instead of silently treating an analysis failure as clean.
    if diagnostic.code not in limits or not isinstance(diagnostic.message, str):
        raise RuntimeError(f"Unexpected Ruff metric diagnostic: {diagnostic.code}")
    measurement = MEASUREMENT_RE.search(diagnostic.message)
    if measurement is None:
        raise RuntimeError(f"Unrecognized Ruff metric message: {diagnostic.message}")
    value, limit = map(int, measurement.groups())
    if limit != limits[diagnostic.code] or value <= limit:
        raise RuntimeError(f"Invalid Ruff metric measurement: {diagnostic.message}")
    symbol = symbols_by_line.get(diagnostic.line)
    if symbol is None:
        raise RuntimeError(f"Cannot locate function for Ruff metric: {diagnostic}")
    return Finding(
        rule=diagnostic.code,
        path=diagnostic.path,
        symbol=symbol,
        line=diagnostic.line,
        value=value,
        limit=limit,
        message=f"{diagnostic.code} {symbol}: {diagnostic.message}",
    )


def check(
    source: str,
    path: Path,
    tree: ast.AST,
    symbols: dict[int, str],
) -> list[Finding]:
    limits = load_limits()
    symbols_by_line = {
        node.lineno: symbols[id(node)]
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    diagnostics = run_check(source, path, build_options(limits))
    return [to_finding(item, limits, symbols_by_line) for item in diagnostics]
