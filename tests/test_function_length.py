import ast
import tempfile
import unittest
from pathlib import Path

from codex_harness.checks.function_length import check
from codex_harness.checks.symbols import build_symbol_index

from .helpers import function_source


class FunctionLengthTests(unittest.TestCase):
    def analyze(self, source: str):
        tree = ast.parse(source)
        return check(
            source=source,
            tree=tree,
            path=Path(tempfile.gettempdir()) / "function_length_case.py",
            max_lines=80,
            symbols=build_symbol_index(tree),
        )

    def test_80_lines_passes(self) -> None:
        self.assertEqual(self.analyze(function_source(80)), [])

    def test_81_lines_reports_cfq001(self) -> None:
        findings = self.analyze(function_source(81))

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].rule, "CFQ001")
        self.assertEqual(findings[0].symbol, "sample")
        self.assertEqual(findings[0].value, 81)

    def test_method_uses_qualified_symbol(self) -> None:
        body = function_source(81, "process").replace("\n", "\n    ").rstrip()
        source = f"class Service:\n    {body}\n"

        findings = self.analyze(source)

        self.assertEqual(findings[0].symbol, "Service.process")

    def test_async_function_is_checked(self) -> None:
        source = function_source(81, "fetch").replace("def fetch", "async def fetch", 1)

        findings = self.analyze(source)

        self.assertEqual((findings[0].rule, findings[0].symbol), ("CFQ001", "fetch"))
