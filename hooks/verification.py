from dataclasses import replace
from pathlib import Path

from ..checks.config.schema import QualityConfig
from ..checks.snapshots import SnapshotChecker, SnapshotStore
from .operations import OperationStore
from .presentation import build_reason, failure_reason
from .retry_state import RetryStore
from .schema import AttemptState, HookResult, HookStatus
from .validation import digest, python_paths


class PostToolHook:
    def __init__(
        self,
        settings: QualityConfig,
        retries: RetryStore,
        snapshots: SnapshotStore,
        checker: SnapshotChecker,
    ) -> None:
        self._settings = settings
        self._retries = retries
        self._snapshots = snapshots
        self._checker = checker

    def process_patch(self, event: dict) -> HookResult:
        scope = self._retries.scope(event)
        operations = OperationStore(scope, self._snapshots)
        with scope.locked():
            state = scope.load()
            previous = operations.get(state, event, self._settings)
            if previous is None:
                raise ValueError("UNKNOWN: no confirmed PreToolUse for this operation")
            files = python_paths(event)
            if previous.result.status == HookStatus.HARNESS_ERROR:
                return previous.result
            if set(previous.files) != {str(path) for path in files}:
                raise ValueError("Baseline file coverage does not match the operation")
            if previous.completed:
                operations.verify_files(previous)
                return previous.result
            if previous.result.blocked:
                raise ValueError("PreToolUse did not authorize this operation")
            fingerprints = operations.fingerprints(files)
            if previous.result.status == HookStatus.NOT_APPLICABLE:
                result = HookResult(
                    HookStatus.NOT_APPLICABLE, "No enabled Python check applies"
                )
            else:
                state, result = self._verify(
                    event, state, scope.snapshot_path(event), previous.files
                )
            if operations.fingerprints(files) != fingerprints:
                raise ValueError("Files changed during verification")
            return operations.save(
                state, event, self._settings, result, fingerprints, completed=True
            )

    def _verify(
        self,
        event: dict,
        state: AttemptState,
        path: Path,
        baseline: dict[str, str | None],
    ) -> tuple[AttemptState, HookResult]:
        maximum = self._settings.max_attempts
        with self._snapshots.consume(path) as claimed:
            if claimed is None:
                raise ValueError("Required baseline is missing or was already consumed")
            snapshot = self._snapshots.read(claimed)
            if set(snapshot.files) != {str(path) for path in python_paths(event)}:
                raise ValueError("Snapshot does not cover the requested Python files")
            actual = {
                name: digest(value["content"]) if value["content"] is not None else None
                for name, value in snapshot.files.items()
            }
            if actual != baseline:
                raise ValueError("Snapshot content differs from confirmed baseline")
            if state.consecutive_failed_attempts >= maximum:
                return state, HookResult(
                    HookStatus.CHECK_FAILED, failure_reason(state, maximum)
                )
            if not self._snapshots.retain_changed(claimed, event):
                return state, HookResult(
                    HookStatus.NOT_APPLICABLE, "No Python content changed"
                )
            regressions = self._checker.check(claimed)
        if not regressions:
            return replace(
                state, consecutive_failed_attempts=0, last_failure=None
            ), HookResult(
                HookStatus.PASS, "Before/after comparison completed without regressions"
            )
        updated = replace(
            state,
            consecutive_failed_attempts=state.consecutive_failed_attempts + 1,
            last_failure=build_reason(regressions),
        )
        return updated, HookResult(
            HookStatus.CHECK_FAILED, failure_reason(updated, maximum)
        )
