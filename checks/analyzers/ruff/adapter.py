import ast

from ...config.schema import ToolConfig
from ...symbols import build_symbol_index
from ..schema import SourceDocument, ToolFinding
from .configuration import METRIC_CODES, build_metric_options, build_regular_options
from .normalization import collapse_nesting, find_symbol, ordinary_finding, to_finding
from .runner import run_check


class RuffAdapter:
    name = "ruff"

    def analyze(
        self,
        documents: tuple[SourceDocument, ...],
        config: ToolConfig,
        *,
        baseline: bool,
    ) -> list[ToolFinding]:
        findings: list[ToolFinding] = []
        for document in documents:
            regular = run_check(
                document.source,
                document.path,
                build_regular_options(config),
                timeout=config.timeout_seconds,
                cwd=document.working_directory,
            )
            findings.extend(
                ordinary_finding(item)
                for item in regular
                if item.code not in METRIC_CODES
            )
            try:
                tree = ast.parse(document.source, filename=str(document.path))
            except SyntaxError:
                continue
            symbols = build_symbol_index(tree)
            functions = [
                node
                for node in ast.walk(tree)
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            ]
            functions.sort(
                key=lambda node: (node.lineno, node.col_offset), reverse=True
            )
            diagnostics = run_check(
                document.source,
                document.path,
                build_metric_options(config),
                timeout=config.timeout_seconds,
                cwd=document.working_directory,
            )
            numeric = collapse_nesting(
                to_finding(item, config.limits, find_symbol(item, functions, symbols))
                for item in diagnostics
            )
            findings.extend(numeric)
        return findings
