import importlib
import json
import sys


def main() -> int:
    runner = None
    event = None
    try:
        event = json.load(sys.stdin)
        runtime = importlib.import_module("codex_harness.hooks.runtime")
        presentation = importlib.import_module("codex_harness.hooks.presentation")
        runner = runtime.HookRuntime()
        result = runner.execute(event, "PostToolUse")
        output = json.dumps(presentation.result_response("PostToolUse", result))
    except (Exception, SystemExit) as exc:
        persistence = ""
        if runner is not None:
            try:
                runner.record_error(event, "PostToolUse")
            except (Exception, SystemExit):
                persistence = "; execution record unavailable (UNKNOWN)"
        reason = f"HARNESS_ERROR: Verification infrastructure failure ({type(exc).__name__}): {exc}{persistence}"
        output = json.dumps(
            {
                "decision": "block",
                "reason": reason,
                "hookSpecificOutput": {
                    "hookEventName": "PostToolUse",
                    "additionalContext": reason,
                },
            }
        )
    try:
        print(output, flush=True)
    except (OSError, ValueError, UnicodeError):
        sys.stdout = None
        try:
            print(
                "HARNESS_ERROR: Unable to deliver hook response",
                file=sys.stderr,
                flush=True,
            )
        except (OSError, ValueError, UnicodeError):
            sys.stderr = None
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
