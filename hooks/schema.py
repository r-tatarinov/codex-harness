from dataclasses import dataclass, field
from enum import StrEnum


class HookStatus(StrEnum):
    PREPARED = "PREPARED"
    PASS = "PASS"
    CHECK_FAILED = "CHECK_FAILED"
    HARNESS_ERROR = "HARNESS_ERROR"
    NOT_APPLICABLE = "NOT_APPLICABLE"


@dataclass(frozen=True)
class HookResult:
    status: HookStatus
    reason: str

    @property
    def blocked(self) -> bool:
        return self.status in (HookStatus.CHECK_FAILED, HookStatus.HARNESS_ERROR)


@dataclass(frozen=True)
class OperationRecord:
    scope: str
    request: str
    policy: str
    result: HookResult
    completed: bool
    files: dict[str, str | None]


@dataclass(frozen=True)
class AttemptState:
    consecutive_failed_attempts: int = 0
    last_failure: str | None = None
    operations: dict[str, OperationRecord] = field(default_factory=dict)
