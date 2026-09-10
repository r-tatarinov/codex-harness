from ...config.schema import ToolConfig
from ..schema import SourceDocument, ToolFinding
from .parsing import parse_output
from .runner import run_check


class MypyAdapter:
    name = "mypy"

    def analyze(
        self,
        documents: tuple[SourceDocument, ...],
        config: ToolConfig,
        *,
        baseline: bool,
    ) -> list[ToolFinding]:
        findings: list[ToolFinding] = []
        for document in documents:
            findings.extend(
                parse_output(run_check(document, config), str(document.path.resolve()))
            )
        return findings
