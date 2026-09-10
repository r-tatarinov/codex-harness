from pathlib import Path

from ..analyzers.orchestrator import AnalyzerOrchestrator
from ..analyzers.schema import SourceDocument, ToolFinding
from ..contracts import RegressionPolicy
from .store import SnapshotStore


class SnapshotChecker:
    def __init__(
        self,
        orchestrator: AnalyzerOrchestrator,
        regression_policy: RegressionPolicy,
        snapshots: SnapshotStore,
    ) -> None:
        self._orchestrator = orchestrator
        self._regression_policy = regression_policy
        self._snapshots = snapshots

    def check(self, snapshot_path: Path) -> list[ToolFinding]:
        snapshot = self._snapshots.read(snapshot_path)
        after_documents = self._snapshots.documents_after(snapshot)
        surviving_paths = {str(document.path) for document in after_documents}

        before_documents = tuple(
            SourceDocument(Path(path), state["content"], snapshot.cwd.resolve())
            for path, state in snapshot.files.items()
            if path in surviving_paths and state["content"] is not None
        )
        before = self._orchestrator.analyze_documents(before_documents, baseline=True)
        after = self._orchestrator.analyze_documents(after_documents)
        return self._regression_policy.compare(before, after)
