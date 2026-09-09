import json
from pathlib import Path

from code_quality import SourceSyntaxError, analyze_source, load_config
from comparison import find_regressions
from finding import Finding


def _analyze_baseline(
    path: Path,
    file_state: dict,
    config: dict,
) -> list[Finding]:
    if not file_state["exists"] or file_state["content"] is None:
        return []

    try:
        return analyze_source(source=file_state["content"], path=path, config=config)
    except SourceSyntaxError:
        # No usable old metrics: apply the limits to the corrected source.
        return []


def check_snapshot(
    snapshot_path: Path,
) -> list[Finding]:
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    config = load_config()

    regressions: list[Finding] = []

    for raw_path, file_state in snapshot["files"].items():
        path = Path(raw_path)
        before = _analyze_baseline(path, file_state, config)
        try:
            source = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            after = []
        else:
            after = analyze_source(source, path, config)
        regressions.extend(find_regressions(before, after))

    return regressions
