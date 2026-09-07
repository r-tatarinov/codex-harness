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
    "PLR1702": ("pylint", "max-nested-blocks"),
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
        "--config",
        "lint.preview=true",
        "--config",
        "lint.explicit-preview-rules=true",
        "--select",
        ",".join(METRIC_SETTINGS),
    ]
    for code, (plugin, setting) in METRIC_SETTINGS.items():
        options.extend(("--config", f"lint.{plugin}.{setting}={limits[code]}"))
    return tuple(options)


def find_symbol(
    diagnostic: RuffFinding,
    functions: list[ast.FunctionDef | ast.AsyncFunctionDef],
    symbols: dict[int, str],
) -> str:
    # Functions are ordered innermost first. PLR1702 points to a block within
    # a function, while C901 and PLR0912 point to its definition.
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
    return Finding(
        rule=diagnostic.code,
        path=diagnostic.path,
        symbol=symbol,
        line=diagnostic.line,
        value=value,
        limit=limit,
        message=f"{diagnostic.code} {symbol}: {diagnostic.message}",
    )


def collapse_nesting(findings: list[Finding]) -> list[Finding]:
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
    return others + sorted(nesting.values(), key=lambda item: item.line)


def check(
    source: str,
    path: Path,
    tree: ast.AST,
    symbols: dict[int, str],
) -> list[Finding]:
    limits = load_limits()
    functions = [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    functions.sort(key=lambda node: (node.lineno, node.col_offset), reverse=True)
    diagnostics = run_check(source, path, build_options(limits))
    findings = [
        to_finding(item, limits, find_symbol(item, functions, symbols))
        for item in diagnostics
    ]
    return collapse_nesting(findings)
