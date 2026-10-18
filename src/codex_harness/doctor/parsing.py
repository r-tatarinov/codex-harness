import json
import re
import shlex
from pathlib import Path

from .schema import Report


def format_report(report: Report) -> str:
    lines = ["Codex Harness Doctor", ""]
    lines.extend(
        f"{item.name:<16} {item.status:<7} {item.detail}" for item in report.checks
    )
    lines.extend(("", f"Result: {report.status}"))
    return "\n".join(lines)


def protocol_result(output: str, event: str) -> tuple[str, bool]:
    raw = json.loads(output)
    if not isinstance(raw, dict):
        raise TypeError("Hook output is not an object")
    specific = raw.get("hookSpecificOutput", {})
    if not isinstance(specific, dict) or specific.get("hookEventName") != event:
        raise ValueError("Incorrect hook response event")
    forbidden = {"suppressOutput", "updatedMCPToolOutput"}
    if event == "PreToolUse":
        forbidden.update(("continue", "stopReason"))
    if forbidden.intersection(raw):
        raise ValueError("Unsupported hook response fields")
    context = specific.get("additionalContext", "")
    if not isinstance(context, str) or ": " not in context:
        raise ValueError("No explicit Harness execution result")
    status = context.split(": ", 1)[0]
    blocked = (
        specific.get("permissionDecision") == "deny"
        if event == "PreToolUse"
        else raw.get("decision") == "block"
    )
    return status, blocked


def command_tokens(value: object) -> list[str]:
    if not isinstance(value, str):
        raise TypeError("Hook command must be a string")
    return shlex.split(value)


def handler_errors(group: dict, handler: dict) -> list[str]:
    errors = []
    allowed = {
        "type",
        "command",
        "commandWindows",
        "command_windows",
        "timeout",
        "statusMessage",
        "async",
        "additionalContextLimit",
    }
    if set(handler) - allowed:
        errors.append("Unsupported Harness handler fields")
    if handler.get("type") != "command":
        errors.append("Harness requires a command handler")
    if handler.get("async", False) is not False:
        errors.append("Mandatory Harness gates must not run asynchronously")
    timeout = handler.get("timeout", 600)
    if type(timeout) not in (int, float) or timeout <= 0:
        errors.append("Hook timeout must be positive")
    matcher = group.get("matcher", "*")
    if not isinstance(matcher, str):
        errors.append("Hook matcher must be a string")
        return errors
    try:
        matches = matcher in ("", "*") or any(
            re.search(matcher, name) for name in ("apply_patch", "Edit", "Write")
        )
    except re.error:
        matches = False
    if not matches:
        errors.append("Matcher does not cover apply_patch; use ^apply_patch$")
    return errors


def hook_tables(raw: object) -> dict:
    if not isinstance(raw, dict) or not isinstance(raw.get("hooks", {}), dict):
        raise TypeError("Invalid hook configuration object")
    return raw.get("hooks", {})


def source_paths(cwd: Path, codex_home: Path) -> tuple[Path, ...]:
    directories = [Path("/etc/codex"), codex_home]
    directories.extend(parent / ".codex" for parent in reversed((cwd, *cwd.parents)))
    return tuple(
        dict.fromkeys(
            directory / name
            for directory in directories
            for name in ("config.toml", "hooks.json")
        )
    )
