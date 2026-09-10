from ..checks.config.schema import QualityConfig
from ..checks.snapshots import SnapshotChecker, SnapshotStore
from .presentation import build_reason, failure_reason
from .retry_state import RetryStore
from .schema import AttemptState


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

    def process_patch(self, event: dict) -> str | None:
        if not self._settings.enabled_tools:
            return None
        maximum = self._settings.max_attempts
        scope = self._retries.scope(event)
        path = scope.snapshot_path(event)
        with scope.locked():
            state = scope.load()
            with self._snapshots.consume(path) as claimed:
                if claimed is None:
                    return None
                if state.consecutive_failed_attempts >= maximum:
                    return failure_reason(state, maximum)
                if not self._snapshots.retain_changed(claimed, event):
                    return None
                regressions = self._checker.check(claimed)

            if not regressions:
                scope.reset()
                return None
            state = AttemptState(
                state.consecutive_failed_attempts + 1, build_reason(regressions)
            )
            scope.save(state)
            return failure_reason(state, maximum)
