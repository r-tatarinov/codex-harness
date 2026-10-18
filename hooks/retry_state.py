import fcntl
import hashlib
import json
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path

from ..checks.storage import AtomicFile
from .parsing import parse_attempts
from .schema import AttemptState
from .validation import identifier


class RetryScope:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._attempts = AtomicFile(path / "attempts.json")

    def snapshot_path(self, event: dict) -> Path:
        tool_id = identifier(event.get("tool_use_id"), "tool_use_id")
        digest = hashlib.sha256(tool_id.encode("utf-8")).hexdigest()
        return self.path / f"patch-{digest}.json"

    @contextmanager
    def locked(self) -> Iterator[None]:
        self.path.mkdir(parents=True, exist_ok=True)
        with (self.path / "scope.lock").open("a", encoding="utf-8") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)

    def load(self) -> AttemptState:
        try:
            state = self._attempts.read_json()
        except FileNotFoundError:
            return AttemptState()
        return parse_attempts(state, self.path.name)

    def save(self, state: AttemptState) -> None:
        self._attempts.write_json({"schema_version": 2, **asdict(state)})


class RetryStore:
    def __init__(self, root: Path, environment: Mapping[str, str]) -> None:
        self._root = root
        self._environment = environment

    def scope(self, event: dict) -> RetryScope:

        if "agent_id" in event or "agent_type" in event:
            raise ValueError(
                "Subagent retry scope unavailable: shared retry budget for subagents "
                "is not supported without a reliable root turn identifier"
            )
        session = event.get("session_id")
        if session is None:
            session = self._environment.get("CODEX_THREAD_ID")
        if session is None:
            session = self._environment.get("CODEX_SESSION_ID")
        values = [
            identifier(session, "session_id"),
            str(Path(identifier(event.get("cwd"), "cwd")).resolve()),
            identifier(event.get("turn_id"), "turn_id"),
        ]
        encoded = json.dumps(values, ensure_ascii=False, separators=(",", ":"))
        digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
        return RetryScope(self._root / "retry" / digest)
