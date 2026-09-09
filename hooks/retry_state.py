"""Small, turn-scoped persistence shared by the apply_patch hooks."""

import fcntl
import hashlib
import json
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path


def identifier(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip() or "\0" in value:
        raise ValueError(f"Missing or invalid {name}; cannot determine retry scope")
    return value


def scope_path(state_dir: Path, event: dict) -> Path:
    # These are explicit agent metadata in the installed hook input schemas.
    # They do not establish a relationship to the root user's turn.
    if "agent_id" in event or "agent_type" in event:
        raise ValueError(
            "Subagent retry scope unavailable: shared retry budget for subagents "
            "is not supported without a reliable root turn identifier"
        )
    session = event.get("session_id")
    if session is None:
        session = os.environ.get("CODEX_THREAD_ID")
    if session is None:
        session = os.environ.get("CODEX_SESSION_ID")
    values = [
        identifier(session, "session_id"),
        str(Path(identifier(event.get("cwd"), "cwd")).resolve()),
        identifier(event.get("turn_id"), "turn_id"),
    ]
    encoded = json.dumps(values, ensure_ascii=False, separators=(",", ":"))
    return state_dir / "retry" / hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def snapshot_path(scope: Path, event: dict) -> Path:
    tool_id = identifier(event.get("tool_use_id"), "tool_use_id")
    digest = hashlib.sha256(tool_id.encode("utf-8")).hexdigest()
    return scope / f"patch-{digest}.json"


@contextmanager
def locked_scope(scope: Path):
    scope.mkdir(parents=True, exist_ok=True)
    with (scope / "scope.lock").open("a", encoding="utf-8") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def atomic_write(path: Path, value: dict) -> None:
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, delete=False
        ) as file:
            temporary = Path(file.name)
            json.dump(value, file, ensure_ascii=False)
            file.flush()
            os.fsync(file.fileno())
        temporary.replace(path)
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                # Cleanup must not turn a committed write into a reported failure.
                pass


def load_attempts(scope: Path) -> dict:
    try:
        state = json.loads((scope / "attempts.json").read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"consecutive_failed_attempts": 0, "last_failure": None}
    if not isinstance(state, dict):
        raise TypeError("Invalid retry state: expected an object")
    count = state.get("consecutive_failed_attempts")
    if type(count) is not int or count < 0:
        raise ValueError("Invalid retry state: consecutive_failed_attempts")
    failure = state["last_failure"]
    if count > 0:
        identifier(failure, "retry state last_failure")
    elif failure is not None and not isinstance(failure, str):
        raise ValueError("Invalid retry state: last_failure")
    return state


def failure_reason(state: dict, maximum: int) -> str:
    count = min(state["consecutive_failed_attempts"], maximum)
    lines = ["Verification failed.", f"Verification attempt {count}/{maximum}"]
    if count >= maximum:
        lines.append("Retry limit reached for the current turn.")
    lines.extend(("", "Last diagnostics:", state["last_failure"]))
    return "\n".join(lines)


def file_state(path: Path) -> dict:
    try:
        content = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {"exists": False, "content": None}
    return {"exists": True, "content": content}


@contextmanager
def consume_snapshot(path: Path):
    # Rename while holding the scope lock. Even an interrupted hook cannot
    # count the same snapshot again on redelivery of PostToolUse.
    claimed = path.with_suffix(".processing")
    try:
        path.replace(claimed)
    except FileNotFoundError:
        yield None
        return
    try:
        yield claimed
    finally:
        claimed.unlink(missing_ok=True)
