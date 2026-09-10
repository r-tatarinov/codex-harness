"""Parse and normalize MyPy's line-delimited JSON diagnostics."""

import json

from ..schema import ToolFinding


def parse_output(output: str, fallback_path: str) -> list[ToolFinding]:
    findings: list[ToolFinding] = []
    for raw_line in output.splitlines():
        if not raw_line.strip():
            continue
        try:
            diagnostic = json.loads(raw_line)
            message = diagnostic["message"]
            code = diagnostic.get("code") or "mypy"
            line = diagnostic.get("line") or 1
            column = diagnostic.get("column") or 1
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            raise RuntimeError("MyPy returned malformed JSON output") from exc
        if not isinstance(code, str) or not isinstance(message, str):
            raise TypeError("MyPy diagnostic code and message must be strings")
        findings.append(
            ToolFinding("mypy", code, message, fallback_path, int(line), int(column))
        )
    return findings
