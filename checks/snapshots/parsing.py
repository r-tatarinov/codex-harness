from pathlib import Path

from .schema import FileState, Snapshot


def parse_snapshot(raw: dict, fallback_cwd: Path) -> Snapshot:
    files: dict[str, FileState] = {}
    for path, state in raw["files"].items():
        if type(state["exists"]) is not bool:
            raise TypeError("Invalid snapshot file existence")
        content = state["content"]
        if not (isinstance(content, str) if state["exists"] else content is None):
            raise ValueError("Invalid snapshot file content")
        files[path] = FileState(exists=state["exists"], content=content)
    return Snapshot(Path(raw.get("cwd", fallback_cwd)), files, raw.get("tool_use_id"))
