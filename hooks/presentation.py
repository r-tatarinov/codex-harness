from ..checks.analyzers.schema import ToolFinding
from .schema import AttemptState


def deny_response(reason: str) -> dict:
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
            "additionalContext": reason,
        }
    }


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


def block_response(reason: str) -> dict:
    return {
        "decision": "block",
        "reason": reason,
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": reason,
        },
    }


def failure_reason(state: AttemptState, maximum: int) -> str:
    count = min(state.consecutive_failed_attempts, maximum)
    lines = ["Verification failed.", f"Verification attempt {count}/{maximum}"]
    if count >= maximum:
        lines.append("Retry limit reached for the current turn.")
    lines.extend(("", "Last diagnostics:", state.last_failure or ""))
    return "\n".join(lines)
