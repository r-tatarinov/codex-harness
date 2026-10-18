from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path

from ..checks.config.schema import QualityConfig
from ..checks.snapshots.store import SnapshotStore
from .retry_state import RetryScope
from .schema import AttemptState, HookResult, OperationRecord
from .validation import digest, policy_digest


class OperationStore:
    def __init__(self, scope: RetryScope, snapshots: SnapshotStore) -> None:
        self._scope = scope
        self._snapshots = snapshots

    def fingerprints(self, paths: Sequence[Path]) -> dict[str, str | None]:
        values = {}
        for path in paths:
            content = self._snapshots.file_state(path)["content"]
            values[str(path)] = digest(content) if content is not None else None
        return values

    def get(
        self, state: AttemptState, event: dict, settings: QualityConfig
    ) -> OperationRecord | None:
        record = state.operations.get(digest(event["tool_use_id"]))
        if record is not None and (
            record.request != digest(event["tool_input"]["command"])
            or record.policy != policy_digest(settings)
        ):
            raise ValueError("Operation input or verification policy has changed")
        return record

    def verify_files(self, record: OperationRecord) -> None:
        if self.fingerprints([Path(name) for name in record.files]) != record.files:
            raise ValueError("Recorded operation does not match current files")

    def save(
        self,
        state: AttemptState,
        event: dict,
        settings: QualityConfig,
        result: HookResult,
        files: dict[str, str | None],
        *,
        completed: bool,
    ) -> HookResult:
        record = OperationRecord(
            self._scope.path.name,
            digest(event["tool_input"]["command"]),
            policy_digest(settings),
            result,
            completed,
            files,
        )
        updated = {**state.operations, digest(event["tool_use_id"]): record}
        self._scope.save(replace(state, operations=updated))
        return result
