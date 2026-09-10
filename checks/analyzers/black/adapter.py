"""Black formatter-check adapter for Harness."""

from ...config.schema import ToolConfig
from ..schema import SourceDocument, ToolFinding
from .runner import run_check


class BlackAdapter:
    name = "black"

    def analyze(
        self,
        documents: tuple[SourceDocument, ...],
        config: ToolConfig,
        *,
        baseline: bool,
    ) -> list[ToolFinding]:
        return [
            ToolFinding(
                "black",
                "BLACK_FORMAT",
                "File would be reformatted",
                str(document.path.resolve()),
                1,
                1,
            )
            for document in documents
            if run_check(document, config)
        ]


ADAPTER = BlackAdapter()
