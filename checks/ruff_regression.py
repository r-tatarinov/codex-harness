import json
from pathlib import Path

from python_ruff import (
    RuffFinding,
    analyze_source,
    find_regressions,
)
from ruff_metrics import METRIC_CODES


def load_snapshot(snapshot_path: Path) -> dict:
    return json.loads(snapshot_path.read_text(encoding="utf-8"))


def analyze_before(
    path: Path,
    file_state: dict,
) -> list[RuffFinding]:
    if not file_state["exists"]:
        return []

    source = file_state["content"]

    if source is None:
        return []

    return analyze_source(
        source=source,
        path=path,
    )


def analyze_after(
    path: Path,
) -> list[RuffFinding]:
    if not path.is_file():
        return []

    source = path.read_text(encoding="utf-8")

    return analyze_source(
        source=source,
        path=path,
    )


def compare_file(
    path: Path,
    file_state: dict,
) -> list[RuffFinding]:
    before = analyze_before(
        path=path,
        file_state=file_state,
    )

    after = analyze_after(
        path=path,
    )

    return find_regressions(
        # The quality pass owns these rules and compares their numeric values.
        before=[item for item in before if item.code not in METRIC_CODES],
        after=[item for item in after if item.code not in METRIC_CODES],
    )


def check_snapshot(
    snapshot_path: Path,
) -> list[RuffFinding]:
    snapshot = load_snapshot(snapshot_path)

    regressions: list[RuffFinding] = []

    for raw_path, file_state in snapshot["files"].items():
        path = Path(raw_path)

        regressions.extend(
            compare_file(
                path=path,
                file_state=file_state,
            )
        )

    return regressions
