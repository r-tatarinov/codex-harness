"""Pylint adapter for the analyzer-neutral Harness interface."""

from ...config.schema import ToolConfig
from ..schema import SourceDocument, ToolFinding
from .parsing import parse_output
from .runner import run_check


class PylintAdapter:
    name = "pylint"

    def analyze(
        self,
        documents: tuple[SourceDocument, ...],
        config: ToolConfig,
        *,
        baseline: bool,
    ) -> list[ToolFinding]:
        findings: list[ToolFinding] = []
        for document in documents:
            path = document.path.resolve()
            findings.extend(parse_output(run_check(document, config), str(path)))
        return findings


ADAPTER = PylintAdapter()
