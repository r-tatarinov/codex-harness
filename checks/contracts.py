from collections.abc import Sequence
from typing import Protocol

from .analyzers.schema import ToolFinding


class RegressionPolicy(Protocol):
    def compare(
        self, before: Sequence[ToolFinding], after: Sequence[ToolFinding]
    ) -> list[ToolFinding]: ...
