from dataclasses import dataclass


@dataclass(frozen=True)
class AttemptState:
    consecutive_failed_attempts: int = 0
    last_failure: str | None = None
