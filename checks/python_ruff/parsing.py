"""Validate Ruff JSON and normalize diagnostic locations and messages."""

import json
from pathlib import Path

from .schema import RuffFinding


def parse_diagnostic(diagnostic: dict, path: Path) -> RuffFinding:
    try:
        code = diagnostic["code"]
        message = diagnostic["message"]
        row = diagnostic["location"]["row"]
        column = diagnostic["location"]["column"]
    except (KeyError, TypeError) as exc:
        raise RuntimeError("Ruff returned a malformed diagnostic") from exc
    if not isinstance(code, str) or not isinstance(message, str):
        raise TypeError("Ruff diagnostic code and message must be strings")
    if type(row) is not int or type(column) is not int or row < 1 or column < 1:
        raise ValueError("Ruff diagnostic location must contain positive integers")
    return RuffFinding(
        code=code, message=message, path=str(path), line=row, column=column
    )


def parse_output(output: str, returncode: int, path: Path) -> list[RuffFinding]:
    try:
        diagnostics = json.loads(output)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Ruff returned invalid JSON") from exc

    if not isinstance(diagnostics, list):
        raise TypeError("Ruff diagnostics must be a JSON array")

    if bool(diagnostics) != (returncode == 1):
        raise RuntimeError("Ruff diagnostics do not match its exit status")
    return [parse_diagnostic(item, path) for item in diagnostics]
