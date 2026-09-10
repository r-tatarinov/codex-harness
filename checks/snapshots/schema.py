from dataclasses import dataclass
from pathlib import Path
from typing import TypedDict


class FileState(TypedDict):
    exists: bool
    content: str | None


@dataclass(frozen=True)
class Snapshot:
    cwd: Path
    files: dict[str, FileState]
    tool_use_id: str | None = None
