import ast

from ...config.schema import ToolConfig
from ...symbols import build_symbol_index
from ..schema import SourceDocument, ToolFinding
from .normalization import find_symbol, to_finding
from .runner import run_metric_check, run_regular_check


class Flake8Adapter:
    name = "flake8"

    def analyze(
        self,
        documents: tuple[SourceDocument, ...],
        config: ToolConfig,
        *,
        baseline: bool,
    ) -> list[ToolFinding]:
        findings: list[ToolFinding] = []
        for document in documents:
            try:
                tree = ast.parse(document.source, filename=str(document.path))
            except SyntaxError as exc:
                if not baseline:
                    findings.append(
                        ToolFinding(
                            "flake8",
                            "SyntaxError",
                            exc.msg,
                            str(document.path.resolve()),
                            exc.lineno or 1,
                            exc.offset or 1,
                        )
                    )
                continue
            findings.extend(run_regular_check(document, config))
            if "CFQ001" not in config.rules.get("select", ()):
                continue
            maximum = config.limits["CFQ001"]
            functions = [
                node
                for node in ast.walk(tree)
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            ]
            symbols = build_symbol_index(tree)
            diagnostics = run_metric_check(
                document.source,
                document.path,
                maximum,
                timeout=config.timeout_seconds,
                cwd=document.working_directory,
            )
            findings.extend(
                to_finding(item, maximum, find_symbol(item, functions, symbols))
                for item in diagnostics
            )
        return findings
