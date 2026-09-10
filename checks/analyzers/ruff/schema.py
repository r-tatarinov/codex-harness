from dataclasses import dataclass


@dataclass(frozen=True)
class RuffFinding:
    code: str
    message: str
    path: str
    line: int
    column: int
