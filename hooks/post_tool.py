#!/usr/bin/env python3

import json
import sys
from pathlib import Path

from ..checks.analyzers.orchestrator import check_snapshot
from ..checks.analyzers.schema import ToolFinding
from ..checks.config import HARNESS_ROOT, load_settings
from .retry_state import (
    atomic_write,
    consume_snapshot,
    failure_reason,
    file_state,
    load_attempts,
    locked_scope,
    scope_path,
    snapshot_path,
)

STATE_DIR = HARNESS_ROOT / "state"


def build_reason(regressions: list[ToolFinding]) -> str:
    lines = ["Code quality regression detected."]
    grouped: dict[str, list[ToolFinding]] = {}
    for finding in regressions:
        grouped.setdefault(finding.tool, []).append(finding)
    for tool, findings in grouped.items():
        lines.append("")
        lines.append(f"{tool}:")
        for finding in findings:
            suffix = ""
            if finding.comparison == "metric":
                suffix = f" [{finding.symbol}: {finding.value} > {finding.limit}]"
            lines.append(
                f"- {finding.path}:{finding.line}:{finding.column}: "
                f"{finding.code} {finding.message}{suffix}"
            )
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
    regressions = check_snapshot(path)
    if regressions:
        return build_reason(regressions)
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
    settings = load_settings()
    maximum = settings.max_attempts
    if not settings.enabled_tools:
        return
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
