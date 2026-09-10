#!/usr/bin/env python3

import json
import re
import sys
from pathlib import Path

from ..checks.code_quality import HARNESS_ROOT, load_max_attempts
from .retry_state import (
    atomic_write,
    failure_reason,
    file_state,
    identifier,
    load_attempts,
    locked_scope,
    scope_path,
    snapshot_path,
)

STATE_DIR = HARNESS_ROOT / "state"

PATCH_FILE_RE = re.compile(
    r"^\*\*\* (?:(?:Add|Update|Delete) File|Move to): (.+?)\s*$",
    re.MULTILINE,
)


def extract_python_files(command: str, cwd: Path) -> list[Path]:
    files: list[Path] = []
    seen: set[Path] = set()

    for raw_path in PATCH_FILE_RE.findall(command):
        path = Path(raw_path.strip())

        if not path.is_absolute():
            path = cwd / path

        path = path.resolve()

        if path.suffix != ".py":
            continue

        if path in seen:
            continue

        seen.add(path)
        files.append(path)

    return files


def emit_deny(reason: str) -> None:
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason,
                    "additionalContext": reason,
                }
            },
            ensure_ascii=False,
        )
    )


def prepare_patch(event: dict) -> None:
    maximum = load_max_attempts()
    scope = scope_path(STATE_DIR, event)
    path = snapshot_path(scope, event)
    with locked_scope(scope):
        state = load_attempts(scope)
        if state["consecutive_failed_attempts"] >= maximum:
            emit_deny(failure_reason(state, maximum))
            return
        command = identifier(event["tool_input"]["command"], "tool_input.command")
        cwd = Path(event["cwd"]).resolve()
        files = extract_python_files(command, cwd)
        if not files:
            return
        snapshot = {
            "tool_use_id": event["tool_use_id"],
            "cwd": str(cwd),
            "files": {str(file): file_state(file) for file in files},
        }
        atomic_write(path, snapshot)


def main() -> int:
    try:
        event = json.load(sys.stdin)
        if event.get("tool_name") == "apply_patch":
            prepare_patch(event)
    except Exception as exc:  # noqa: BLE001 -- fail closed at the hook boundary
        # A hook boundary: checker/configuration bugs must deny the patch too.
        emit_deny(f"Verification infrastructure failure: {type(exc).__name__}: {exc}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
