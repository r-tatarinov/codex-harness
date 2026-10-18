from dataclasses import dataclass
from pathlib import Path
from typing import Literal

DoctorStatus = Literal["PASS", "FAIL", "UNKNOWN"]


@dataclass(frozen=True)
class Check:
    name: str
    status: DoctorStatus
    detail: str


@dataclass(frozen=True)
class Installation:
    python: Path
    pre: Path
    post: Path
    version: str


@dataclass(frozen=True)
class Report:
    checks: tuple[Check, ...]

    @property
    def status(self) -> DoctorStatus:
        if any(check.status == "FAIL" for check in self.checks):
            return "FAIL"
        if any(check.status == "UNKNOWN" for check in self.checks):
            return "UNKNOWN"
        return "PASS"

    @property
    def exit_code(self) -> int:
        return {"PASS": 0, "FAIL": 1, "UNKNOWN": 2}[self.status]
