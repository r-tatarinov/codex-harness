#!/usr/bin/env python3

import json
import sys
from pathlib import Path


HARNESS_ROOT = Path.home() / ".codex" / "harness"
CHECKS_DIR = HARNESS_ROOT / "checks"
STATE_DIR = HARNESS_ROOT / "state"

sys.path.insert(0, str(CHECKS_DIR))

from regression import check_snapshot as check_quality_snapshot
from ruff_regression import check_snapshot as check_ruff_snapshot


def build_quality_lines(regressions: list) -> list[str]:
    lines: list[str] = []

    for finding in regressions:
        lines.append(
            f"- {finding.path}:{finding.line}: "
            f"{finding.message}"
        )

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
    lines = [
        "Code quality regression detected.",
        "",
        "Fix the following issues before continuing:",
    ]

    if quality_regressions:
        lines.append("")
        lines.append("Quality rules:")
        lines.extend(
            build_quality_lines(quality_regressions)
        )

    if ruff_regressions:
        lines.append("")
        lines.append("Ruff:")
        lines.extend(
            build_ruff_lines(ruff_regressions)
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
        quality_regressions = check_quality_snapshot(
            snapshot_path
        )

        ruff_regressions = check_ruff_snapshot(
            snapshot_path
        )

        if quality_regressions or ruff_regressions:
            emit_block(
                build_reason(
                    quality_regressions=quality_regressions,
                    ruff_regressions=ruff_regressions,
                )
            )

    except (
        OSError,
        SyntaxError,
        ValueError,
        KeyError,
        RuntimeError,
    ) as exc:
        emit_block(
            f"Code quality analysis failed: {exc}"
        )

    finally:
        snapshot_path.unlink(
            missing_ok=True,
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())

