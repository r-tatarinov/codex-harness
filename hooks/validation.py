import hashlib
import json
import re
from dataclasses import asdict
from pathlib import Path

from ..checks.config.schema import QualityConfig


def identifier(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip() or "\0" in value:
        raise ValueError(f"Missing or invalid {name}; cannot determine retry scope")
    return value


def validate_event(value: object, event_name: str) -> dict:
    if not isinstance(value, dict):
        raise TypeError("Hook input must be a JSON object")
    if value.get("hook_event_name") != event_name:
        raise ValueError("hook_event_name does not match the entry point")
    identifier(value.get("tool_name"), "tool_name")
    if value["tool_name"] == "apply_patch":
        identifier(value.get("cwd"), "cwd")
        identifier(value.get("tool_use_id"), "tool_use_id")
        if not isinstance(value.get("tool_input"), dict):
            raise ValueError("tool_input must be an object")
        identifier(value["tool_input"].get("command"), "tool_input.command")
    return value


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def policy_digest(settings: QualityConfig) -> str:
    return digest(json.dumps(asdict(settings), sort_keys=True))


def python_paths(event: dict) -> list[Path]:
    command = event["tool_input"]["command"]
    lines = command.strip().splitlines()
    if not lines or lines[0] != "*** Begin Patch" or lines[-1] != "*** End Patch":
        raise ValueError("Cannot determine files from malformed apply_patch input")
    paths = re.findall(
        r"^\*\*\* (?:(?:Add|Update|Delete) File|Move to): (.+?)\s*$",
        command,
        re.MULTILINE,
    )
    cwd = Path(event["cwd"]).resolve()
    resolved = [(cwd / name.strip()).resolve() for name in paths]
    return list(dict.fromkeys(path for path in resolved if path.suffix == ".py"))
