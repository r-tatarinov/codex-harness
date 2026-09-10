"""Parse and normalize Pylint JSON2 diagnostics."""

import json

from ...config.schema import ConfigurationError
from ..schema import ToolFinding


def parse_output(output: str, path: str) -> list[ToolFinding]:
    try:
        payload = json.loads(output)
        diagnostics = payload["messages"] if isinstance(payload, dict) else payload
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise RuntimeError("Pylint returned invalid JSON2 output") from exc
    if not isinstance(diagnostics, list):
        raise TypeError("Pylint diagnostics must be an array")
    findings: list[ToolFinding] = []
    for diagnostic in diagnostics:
        try:
            code = diagnostic["messageId"]
            message = diagnostic["message"]
            line = diagnostic["line"]
            column = diagnostic["column"] + 1
        except (KeyError, TypeError) as exc:
            raise RuntimeError("Pylint returned a malformed diagnostic") from exc
        if not isinstance(code, str) or not isinstance(message, str):
            raise TypeError("Pylint diagnostic text must be strings")
        if code == "W0012" and diagnostic.get("module") == "Command line":
            raise ConfigurationError(f"tools.pylint.rules: {message}")
        findings.append(ToolFinding("pylint", code, message, path, line, column))
    return findings
