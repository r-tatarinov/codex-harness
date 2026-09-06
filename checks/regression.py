import json
from pathlib import Path

from code_quality import analyze_source, load_config
from comparison import find_regressions
from finding import Finding


def load_snapshot(snapshot_path: Path) -> dict:
    return json.loads(
        snapshot_path.read_text(encoding="utf-8")
    )


def analyze_before(
    path: Path,
    file_state: dict,
    config: dict,
) -> list[Finding]:
    if not file_state["exists"]:
        return []

    source = file_state["content"]

    if source is None:
        return []

    return analyze_source(
        source=source,
        path=path,
        config=config,
    )


def analyze_after(
    path: Path,
    config: dict,
) -> list[Finding]:
    if not path.is_file():
        return []

    source = path.read_text(encoding="utf-8")

    return analyze_source(
        source=source,
        path=path,
        config=config,
    )


def compare_file(
    path: Path,
    file_state: dict,
    config: dict,
) -> list[Finding]:
    before = analyze_before(
        path=path,
        file_state=file_state,
        config=config,
    )

    after = analyze_after(
        path=path,
        config=config,
    )

    return find_regressions(
        before=before,
        after=after,
    )


def check_snapshot(
    snapshot_path: Path,
) -> list[Finding]:
    snapshot = load_snapshot(snapshot_path)
    config = load_config()

    regressions: list[Finding] = []

    for raw_path, file_state in snapshot["files"].items():
        path = Path(raw_path)

        regressions.extend(
            compare_file(
                path=path,
                file_state=file_state,
                config=config,
            )
        )

    return regressions

