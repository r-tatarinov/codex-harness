#!/usr/bin/env python3

import json
import sys
from pathlib import Path

HARNESS_ROOT = Path.home() / ".codex" / "harness"
CHECKS_DIR = HARNESS_ROOT / "checks"
STATE_DIR = HARNESS_ROOT / "state"

sys.path.insert(0, str(CHECKS_DIR))

from code_quality import SourceSyntaxError, load_max_attempts
from regression import check_snapshot as check_quality_snapshot
from retry_state import (
    atomic_write,
    consume_snapshot,
    failure_reason,
    file_state,
    load_attempts,
    locked_scope,
    scope_path,
    snapshot_path,
)
from ruff_regression import check_snapshot as check_ruff_snapshot


def build_quality_lines(regressions: list) -> list[str]:
    lines: list[str] = []

    for finding in regressions:
        lines.append(f"- {finding.path}:{finding.line}: {finding.message}")

    return lines


def build_ruff_lines(regressions: list) -> list[str]:
    lines: list[str] = []

    for finding in regressions:
        lines.append(
            f"- {finding.path}:{finding.line}:{finding.column}: "
            f"{finding.code} {finding.message}"
        )

    return lines


def build_reason(
    quality_regressions: list,
    ruff_regressions: list,
) -> str:
    lines = ["Code quality regression detected."]

    if quality_regressions:
        lines.append("")
        lines.append("Quality rules:")
        lines.extend(build_quality_lines(quality_regressions))

    if ruff_regressions:
        lines.append("")
        lines.append("Ruff:")
        lines.extend(build_ruff_lines(ruff_regressions))

    return "\n".join(lines)


def emit_block(reason: str) -> None:
    response = {
        "decision": "block",
        "reason": reason,
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": reason,
        },
    }

    print(
        json.dumps(
            response,
            ensure_ascii=False,
        )
    )


def verify_snapshot(path: Path) -> str | None:
    try:
        quality_regressions = check_quality_snapshot(path)
    except SourceSyntaxError as exc:
        return str(exc)
    ruff_regressions = check_ruff_snapshot(path)
    if quality_regressions or ruff_regressions:
        return build_reason(quality_regressions, ruff_regressions)
    return None


def retain_changed_files(path: Path, event: dict) -> bool:
    snapshot = json.loads(path.read_text(encoding="utf-8"))
    if snapshot["tool_use_id"] != event["tool_use_id"]:
        raise ValueError("Snapshot tool_use_id does not match the hook")
    if snapshot["cwd"] != str(Path(event["cwd"]).resolve()):
        raise ValueError("Snapshot cwd does not match the hook")
    changed = {}
    for raw_path, before in snapshot["files"].items():
        if type(before["exists"]) is not bool:
            raise TypeError("Invalid snapshot file existence")
        expected = (
            isinstance(before["content"], str)
            if before["exists"]
            else (before["content"] is None)
        )
        if not expected:
            raise ValueError("Invalid snapshot file content")
        if file_state(Path(raw_path)) != before:
            changed[raw_path] = before
    if not changed:
        return False
    snapshot["files"] = changed
    atomic_write(path, snapshot)
    return True


def process_patch(event: dict) -> None:
    maximum = load_max_attempts()
    scope = scope_path(STATE_DIR, event)
    path = snapshot_path(scope, event)
    with locked_scope(scope):
        state = load_attempts(scope)
        with consume_snapshot(path) as claimed:
            if claimed is None:
                return
            if state["consecutive_failed_attempts"] >= maximum:
                emit_block(failure_reason(state, maximum))
                return
            if not retain_changed_files(claimed, event):
                return
            failure = verify_snapshot(claimed)
        # Consume the snapshot before committing the result. Infrastructure
        # failures above leave both the counter and last diagnostics untouched.
        if failure is None:
            (scope / "attempts.json").unlink(missing_ok=True)
            return
        state = {
            "consecutive_failed_attempts": state["consecutive_failed_attempts"] + 1,
            "last_failure": failure,
        }
        atomic_write(scope / "attempts.json", state)
        emit_block(failure_reason(state, maximum))


def main() -> int:
    try:
        event = json.load(sys.stdin)
        if event.get("tool_name") == "apply_patch":
            process_patch(event)
    except Exception as exc:  # noqa: BLE001 -- fail closed at the hook boundary
        # Source parsing errors are classified only inside verify_snapshot.
        emit_block(f"Verification infrastructure failure: {type(exc).__name__}: {exc}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
