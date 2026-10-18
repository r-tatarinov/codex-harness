import os

from ..checks.analyzers.orchestrator import AnalyzerOrchestrator
from ..checks.analyzers.registry import BUILTIN_ANALYZERS
from ..checks.config import CONFIG_PATH, HARNESS_ROOT
from ..checks.config.loader import ConfigurationLoader
from ..checks.regression import DefaultRegressionPolicy
from ..checks.snapshots import SnapshotChecker, SnapshotStore
from .operations import OperationStore
from .preparation import PreToolHook
from .retry_state import RetryStore
from .schema import HookResult, HookStatus
from .validation import validate_event
from .verification import PostToolHook


class HookRuntime:
    def execute(self, raw: object, event_name: str) -> HookResult:
        event = validate_event(raw, event_name)
        if event["tool_name"] != "apply_patch":
            return HookResult(
                HookStatus.NOT_APPLICABLE, "Tool is outside the apply_patch policy"
            )
        settings = ConfigurationLoader(CONFIG_PATH).load()
        snapshots = SnapshotStore()
        retries = RetryStore(HARNESS_ROOT / "state", os.environ)
        if event_name == "PreToolUse":
            return PreToolHook(settings, retries, snapshots).prepare_patch(event)
        checker = SnapshotChecker(
            AnalyzerOrchestrator(settings, (cls() for cls in BUILTIN_ANALYZERS)),
            DefaultRegressionPolicy(),
            snapshots,
        )
        return PostToolHook(settings, retries, snapshots, checker).process_patch(event)

    def record_error(self, raw: object, event_name: str) -> None:
        event = validate_event(raw, event_name)
        if event["tool_name"] != "apply_patch":
            return
        settings = ConfigurationLoader(CONFIG_PATH).load()
        scope = RetryStore(HARNESS_ROOT / "state", os.environ).scope(event)
        with scope.locked():
            state = scope.load()
            operations = OperationStore(scope, SnapshotStore())
            previous = operations.get(state, event, settings)
            if previous is not None and previous.completed:
                return
            operations.save(
                state,
                event,
                settings,
                HookResult(
                    HookStatus.HARNESS_ERROR,
                    "Verification did not complete; start a new operation",
                ),
                previous.files if previous else {},
                completed=event_name == "PostToolUse",
            )
