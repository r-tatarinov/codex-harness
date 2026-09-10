"""Normalized shape of one Ruff diagnostic."""

from dataclasses import dataclass


@dataclass(frozen=True)
class RuffFinding:
    code: str
    message: str
    path: str
    line: int
    column: int

    @property
    def key(self) -> tuple[str, str]:
        return self.code, self.message
