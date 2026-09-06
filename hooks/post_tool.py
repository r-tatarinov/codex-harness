#!/usr/bin/env python3

import json
import sys
from pathlib import Path


HARNESS_ROOT = Path.home() / ".codex" / "harness"
CHECKS_DIR = HARNESS_ROOT / "checks"
STATE_DIR = HARNESS_ROOT / "state"

sys.path.insert(0, str(CHECKS_DIR))

from regression import check_snapshot


def build_reason(regressions: list) -> str:
    lines = [
        "Code quality regression detected.",
        "",
        "Fix the following issues before continuing:",
    ]

    for finding in regressions:
        lines.append(
            f"- {finding.path}:{finding.line}: {finding.message}"
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


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, TypeError):
        return 0

    if event.get("tool_name") != "apply_patch":
        return 0

    tool_use_id = event.get("tool_use_id")

    if not tool_use_id:
        return 0

    snapshot_path = STATE_DIR / f"{tool_use_id}.json"

    if not snapshot_path.is_file():
        return 0

    try:
        regressions = check_snapshot(snapshot_path)

        if regressions:
            emit_block(
                build_reason(regressions)
            )

    except (OSError, SyntaxError, ValueError, KeyError) as exc:
        emit_block(
            f"Code quality analysis failed: {exc}"
        )

    finally:
        snapshot_path.unlink(missing_ok=True)

    return 0


if __name__ == "__main__":
    sys.exit(main())

