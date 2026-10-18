from pathlib import Path

from ..checks.config.schema import QualityConfig
from ..checks.snapshots.store import SnapshotStore
from .operations import OperationStore
from .presentation import failure_reason
from .retry_state import RetryStore
from .schema import HookResult, HookStatus
from .validation import python_paths


class PreToolHook:
    def __init__(
        self, settings: QualityConfig, retries: RetryStore, snapshots: SnapshotStore
    ) -> None:
        self._settings = settings
        self._retries = retries
        self._snapshots = snapshots

    def prepare_patch(self, event: dict) -> HookResult:
        scope = self._retries.scope(event)
        path = scope.snapshot_path(event)
        operations = OperationStore(scope, self._snapshots)
        with scope.locked():
            state = scope.load()
            if self._settings.enabled_tools and (
                state.consecutive_failed_attempts >= self._settings.max_attempts
            ):
                return HookResult(
                    HookStatus.CHECK_FAILED,
                    failure_reason(state, self._settings.max_attempts),
                )
            previous = operations.get(state, event, self._settings)
            if previous is not None:
                if previous.completed or previous.result.blocked:
                    raise ValueError("Operation identifier has already been used")
                operations.verify_files(previous)
                if previous.result.status == HookStatus.PREPARED and not path.is_file():
                    raise ValueError("Prepared operation has no baseline")
                return previous.result
            files = python_paths(event)
            if path.exists() or path.with_suffix(".processing").exists():
                raise ValueError("Unconfirmed or interrupted baseline already exists")
            fingerprints = operations.fingerprints(files)
            if files and self._settings.enabled_tools:
                snapshot = self._snapshots.capture(
                    files, Path(event["cwd"]).resolve(), event["tool_use_id"]
                )
                self._snapshots.write(path, snapshot)
                if operations.fingerprints(files) != fingerprints:
                    raise ValueError("Files changed during baseline capture")
                result = HookResult(
                    HookStatus.PREPARED, "Baseline captured; verification pending"
                )
            else:
                result = HookResult(
                    HookStatus.NOT_APPLICABLE, "No enabled Python check applies"
                )
            return operations.save(
                state, event, self._settings, result, fingerprints, completed=False
            )
