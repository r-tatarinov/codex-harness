#!/usr/bin/env python3

import json
import re
import sys
from pathlib import Path


HARNESS_ROOT = Path.home() / ".codex" / "harness"
STATE_DIR = HARNESS_ROOT / "state"

PATCH_FILE_RE = re.compile(
    r"^\*\*\* (?:Add|Update|Delete) File: (.+?)\s*$",
    re.MULTILINE,
)


def extract_python_files(command: str, cwd: Path) -> list[Path]:
    files: list[Path] = []
    seen: set[Path] = set()

    for raw_path in PATCH_FILE_RE.findall(command):
        path = Path(raw_path.strip())

        if not path.is_absolute():
            path = cwd / path

        path = path.resolve()

        if path.suffix != ".py":
            continue

        if path in seen:
            continue

        seen.add(path)
        files.append(path)

    return files


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, TypeError):
        return 0

    if event.get("tool_name") != "apply_patch":
        return 0

    tool_use_id = event.get("tool_use_id")

    if not tool_use_id:
        return 0

    cwd = Path(event.get("cwd", ".")).resolve()

    tool_input = event.get("tool_input") or {}
    command = tool_input.get("command", "")

    if not command:
        return 0

    python_files = extract_python_files(
        command=command,
        cwd=cwd,
    )

    if not python_files:
        return 0

    snapshot = {
        "tool_use_id": tool_use_id,
        "cwd": str(cwd),
        "files": {},
    }

    for path in python_files:
        if path.is_file():
            try:
                content = path.read_text(encoding="utf-8")
            except OSError:
                continue

            snapshot["files"][str(path)] = {
                "exists": True,
                "content": content,
            }
        else:
            snapshot["files"][str(path)] = {
                "exists": False,
                "content": None,
            }

    STATE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    snapshot_path = STATE_DIR / f"{tool_use_id}.json"

    snapshot_path.write_text(
        json.dumps(
            snapshot,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())

