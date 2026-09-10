"""Parse Flake8's stable delimiter output."""

from pathlib import Path

from ..schema import ToolFinding
from .schema import Flake8Finding

DELIMITER = "\x1f"
OUTPUT_FORMAT = DELIMITER.join(("%(row)d", "%(col)d", "%(code)s", "%(text)s"))


def _positive_integer(raw_value: str, name: str) -> int:
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise RuntimeError(f"Flake8 returned an invalid {name}") from exc
    if value < 1:
        raise RuntimeError(f"Flake8 returned an invalid {name}")
    return value


def parse_metric_output(
    output: str, returncode: int, path: Path
) -> list[Flake8Finding]:
    findings = []
    for raw_line in output.splitlines():
        parts = raw_line.split(DELIMITER, maxsplit=3)
        if len(parts) != 4:
            raise RuntimeError("Flake8 returned a malformed diagnostic")
        row, column, code, message = parts
        if code != "CFQ001" or not message:
            raise RuntimeError("Flake8 returned an unexpected diagnostic")
        findings.append(
            Flake8Finding(
                code,
                message,
                str(path),
                _positive_integer(row, "row"),
                _positive_integer(column, "column"),
            )
        )
    if bool(findings) != (returncode == 1):
        raise RuntimeError("Flake8 diagnostics do not match its exit status")
    return findings


def parse_regular_output(output: str, returncode: int, path: Path) -> list[ToolFinding]:
    findings: list[ToolFinding] = []
    for raw_line in output.splitlines():
        parts = raw_line.split(DELIMITER, maxsplit=3)
        if len(parts) != 4:
            raise RuntimeError("Flake8 returned a malformed diagnostic")
        row, column, code, message = parts
        findings.append(
            ToolFinding(
                "flake8",
                code,
                message,
                str(path),
                _positive_integer(row, "row"),
                _positive_integer(column, "column"),
            )
        )
    if bool(findings) != (returncode == 1):
        raise RuntimeError("Flake8 diagnostics do not match its exit status")
    return findings
