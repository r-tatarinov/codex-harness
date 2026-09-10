from collections.abc import Iterable
from pathlib import Path

from ..config.schema import QualityConfig
from .base import AnalyzerAdapter
from .schema import SourceDocument, ToolFinding


class AnalyzerOrchestrator:
    def __init__(
        self, settings: QualityConfig, adapters: Iterable[AnalyzerAdapter]
    ) -> None:
        registered = {adapter.name: adapter for adapter in adapters}
        self._analyzers = tuple(
            (registered[tool.name], tool) for tool in settings.enabled_tools
        )

    def analyze_documents(
        self, documents: tuple[SourceDocument, ...], *, baseline: bool = False
    ) -> list[ToolFinding]:
        if not documents:
            return []
        return [
            finding
            for adapter, config in self._analyzers
            for finding in adapter.analyze(documents, config, baseline=baseline)
        ]

    def analyze_files(self, paths: Iterable[Path]) -> list[ToolFinding]:
        cwd = Path.cwd()
        documents = tuple(
            SourceDocument(path.resolve(), path.read_text(encoding="utf-8"), cwd)
            for path in paths
            if path.suffix == ".py" and path.is_file()
        )
        return self.analyze_documents(documents)
