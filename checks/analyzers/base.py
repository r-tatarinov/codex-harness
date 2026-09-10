from typing import Protocol

from ..config.schema import ToolConfig
from .schema import SourceDocument, ToolFinding


class AnalyzerAdapter(Protocol):
    name: str

    def analyze(
        self,
        documents: tuple[SourceDocument, ...],
        config: ToolConfig,
        *,
        baseline: bool,
    ) -> list[ToolFinding]: ...


class AnalyzerConfigurationPolicy(Protocol):
    def validate(self, config: ToolConfig) -> None: ...
