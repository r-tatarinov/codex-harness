"""Compare Ruff diagnostics by code, message and occurrence count."""

import json
from collections import Counter
from collections.abc import Iterable
from pathlib import Path

from python_ruff import RuffFinding, analyze_source
from ruff_metrics import METRIC_CODES


def find_regressions(
    before: Iterable[RuffFinding],
    after: Iterable[RuffFinding],
) -> list[RuffFinding]:
    before_counts = Counter(finding.key for finding in before)

    regressions: list[RuffFinding] = []

    for finding in after:
        if before_counts[finding.key] > 0:
            before_counts[finding.key] -= 1
            continue

        regressions.append(finding)

    return regressions


def check_snapshot(
    snapshot_path: Path,
) -> list[RuffFinding]:
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))

    regressions: list[RuffFinding] = []

    for raw_path, file_state in snapshot["files"].items():
        path = Path(raw_path)
        before = []
        if file_state["exists"] and file_state["content"] is not None:
            before = analyze_source(file_state["content"], path)
        try:
            source = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            after = []
        else:
            after = analyze_source(source, path)
        regressions.extend(
            # The quality pass owns these rules and compares their numeric values.
            find_regressions(
                before=(item for item in before if item.code not in METRIC_CODES),
                after=(item for item in after if item.code not in METRIC_CODES),
            ),
        )

    return regressions
