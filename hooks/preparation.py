import re
from pathlib import Path

from ..checks.config.schema import QualityConfig
from ..checks.snapshots import SnapshotStore
from .presentation import failure_reason
from .retry_state import RetryStore
from .validation import identifier

PATCH_FILE_RE = re.compile(
    r"^\*\*\* (?:(?:Add|Update|Delete) File|Move to): (.+?)\s*$",
    re.MULTILINE,
)


class PreToolHook:
    def __init__(
        self, settings: QualityConfig, retries: RetryStore, snapshots: SnapshotStore
    ) -> None:
        self._settings = settings
        self._retries = retries
        self._snapshots = snapshots

    def _extract_python_files(self, command: str, cwd: Path) -> list[Path]:
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

    def prepare_patch(self, event: dict) -> str | None:
        if not self._settings.enabled_tools:
            return None
        maximum = self._settings.max_attempts
        scope = self._retries.scope(event)
        path = scope.snapshot_path(event)
        with scope.locked():
            state = scope.load()
            if state.consecutive_failed_attempts >= maximum:
                return failure_reason(state, maximum)
            command = identifier(event["tool_input"]["command"], "tool_input.command")
            cwd = Path(event["cwd"]).resolve()
            files = self._extract_python_files(command, cwd)
            if files:
                snapshot = self._snapshots.capture(files, cwd, event["tool_use_id"])
                self._snapshots.write(path, snapshot)
        return None
