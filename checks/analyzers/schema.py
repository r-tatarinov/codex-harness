"""Stable types shared by all external analyzer adapters."""

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

ComparisonKind = Literal["occurrence", "metric"]


@dataclass(frozen=True)
class SourceDocument:
    path: Path
    source: str
    cwd: Path | None = None

    @property
    def working_directory(self) -> Path:
        return self.cwd or self.path.resolve().parent


@dataclass(frozen=True)
class ToolFinding:
    tool: str
    code: str
    message: str
    path: str
    line: int
    column: int = 1
    comparison: ComparisonKind = "occurrence"
    symbol: str | None = None
    value: int | None = None
    limit: int | None = None

    @property
    def occurrence_key(self) -> tuple[str, str, str]:
        return self.tool, self.code, self.message

    @property
    def metric_key(self) -> tuple[str, str, str | None]:
        return self.tool, self.code, self.symbol

    def __post_init__(self) -> None:
        if self.line < 1 or self.column < 1:
            raise ValueError("finding locations must be positive")
        if self.comparison == "metric" and (
            self.symbol is None or self.value is None or self.limit is None
        ):
            raise ValueError("metric findings require symbol, value, and limit")
