import json
import os
import sys

from ..checks.config import (
    CONFIG_PATH,
    HARNESS_ROOT,
)
from ..checks.config.loader import ConfigurationLoader
from ..checks.snapshots import SnapshotStore
from .preparation import PreToolHook
from .presentation import deny_response
from .retry_state import RetryStore


def main() -> int:
    try:
        event = json.load(sys.stdin)
        if event.get("tool_name") == "apply_patch":
            hook = PreToolHook(
                ConfigurationLoader(CONFIG_PATH).load(),
                RetryStore(HARNESS_ROOT / "state", os.environ),
                SnapshotStore(),
            )
            reason = hook.prepare_patch(event)
            if reason is not None:
                print(json.dumps(deny_response(reason), ensure_ascii=False))
    except Exception as exc:

        reason = f"Verification infrastructure failure: {type(exc).__name__}: {exc}"
        print(json.dumps(deny_response(reason), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
