"""Load configured adapters and apply the shared regression policy."""

import json
from pathlib import Path

from ..config import QualityConfig, load_settings
from .comparison import find_regressions
from .registry import get_adapter
from .schema import SourceDocument, ToolFinding


def _documents_before(snapshot: dict) -> tuple[SourceDocument, ...]:
    documents = []
    cwd = Path(snapshot.get("cwd", Path.cwd())).resolve()
    for raw_path, state in snapshot["files"].items():
        path = Path(raw_path)
        if state["exists"] and state["content"] is not None and path.exists():
            documents.append(SourceDocument(path, state["content"], cwd))
    return tuple(documents)


def _documents_after(snapshot: dict) -> tuple[SourceDocument, ...]:
    documents = []
    cwd = Path(snapshot.get("cwd", Path.cwd())).resolve()
    for raw_path in snapshot["files"]:
        path = Path(raw_path)
        try:
            source = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            continue
        documents.append(SourceDocument(path, source, cwd))
    return tuple(documents)


def analyze_documents(
    documents: tuple[SourceDocument, ...],
    settings: QualityConfig,
) -> list[ToolFinding]:
    findings: list[ToolFinding] = []
    for tool in settings.enabled_tools:
        findings.extend(get_adapter(tool.name).analyze(documents, tool, baseline=False))
    return findings


def analyze_files(
    paths: list[Path], settings: QualityConfig | None = None
) -> list[ToolFinding]:
    documents = tuple(
        SourceDocument(path.resolve(), path.read_text(encoding="utf-8"), Path.cwd())
        for path in paths
        if path.suffix == ".py" and path.is_file()
    )
    return analyze_documents(documents, settings or load_settings())


def check_snapshot(
    snapshot_path: Path, settings: QualityConfig | None = None
) -> list[ToolFinding]:
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    active = settings or load_settings()
    before_documents = _documents_before(snapshot)
    after_documents = _documents_after(snapshot)
    regressions: list[ToolFinding] = []
    for tool in active.enabled_tools:
        adapter = get_adapter(tool.name)
        before = adapter.analyze(before_documents, tool, baseline=True)
        after = adapter.analyze(after_documents, tool, baseline=False)
        regressions.extend(find_regressions(before, after))
    return regressions
