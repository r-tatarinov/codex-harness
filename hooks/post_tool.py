import json
import os
import sys

from ..checks.analyzers.orchestrator import AnalyzerOrchestrator
from ..checks.analyzers.registry import BUILTIN_ANALYZERS
from ..checks.config import (
    CONFIG_PATH,
    HARNESS_ROOT,
)
from ..checks.config.loader import ConfigurationLoader
from ..checks.regression import DefaultRegressionPolicy
from ..checks.snapshots import SnapshotChecker, SnapshotStore
from .presentation import block_response
from .retry_state import RetryStore
from .verification import PostToolHook


def main() -> int:
    try:
        event = json.load(sys.stdin)
        if event.get("tool_name") == "apply_patch":
            settings = ConfigurationLoader(CONFIG_PATH).load()
            snapshots = SnapshotStore()
            checker = SnapshotChecker(
                AnalyzerOrchestrator(settings, (cls() for cls in BUILTIN_ANALYZERS)),
                DefaultRegressionPolicy(),
                snapshots,
            )
            hook = PostToolHook(
                settings,
                RetryStore(HARNESS_ROOT / "state", os.environ),
                snapshots,
                checker,
            )
            reason = hook.process_patch(event)
            if reason is not None:
                print(json.dumps(block_response(reason), ensure_ascii=False))
    except Exception as exc:
        reason = f"Verification infrastructure failure: {type(exc).__name__}: {exc}"
        print(json.dumps(block_response(reason), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
