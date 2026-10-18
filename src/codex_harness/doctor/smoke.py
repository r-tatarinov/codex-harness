import json
import os
import subprocess
import tempfile
import uuid
from pathlib import Path

from ..checks.storage import AtomicFile
from .parsing import protocol_result
from .schema import Check, Installation


class RuntimeSmoke:
    def __init__(self, installation: Installation) -> None:
        self._installation = installation

    def run(self) -> list[Check]:
        with tempfile.TemporaryDirectory(prefix="harness-doctor-") as directory:
            root = Path(directory)
            environment = {
                key: value
                for key, value in os.environ.items()
                if not key.startswith("PYTHON")
            }
            environment.update(HOME=directory, CODEX_HOME=str(root / ".codex"))
            project = root / "project"
            project.mkdir()
            file = project / "probe.py"
            file.write_text("value = 1\n", encoding="utf-8")
            event = {
                "session_id": str(uuid.uuid4()),
                "turn_id": "doctor",
                "tool_use_id": "probe",
                "cwd": str(project),
                "tool_name": "apply_patch",
                "tool_input": {
                    "command": "*** Begin Patch\n*** Update File: probe.py\n@@\n-value = 1\n+value = 2\n*** End Patch"
                },
            }
            self._call(event, "PreToolUse", "PREPARED", False, environment, root)
            if len(list((root / ".codex/harness/state").rglob("patch-*.json"))) != 1:
                raise ValueError("PreToolUse did not create a baseline")
            file.write_text("value = 2\n", encoding="utf-8")
            self._call(event, "PostToolUse", "PASS", False, environment, root)
            self._call(event, "PostToolUse", "PASS", False, environment, root)
            event["tool_use_id"] = "regression"
            self._call(event, "PreToolUse", "PREPARED", False, environment, root)
            file.write_text("import os\nvalue = 2\n", encoding="utf-8")
            self._call(event, "PostToolUse", "CHECK_FAILED", True, environment, root)
            for name in ("PreToolUse", "PostToolUse"):
                self._call({}, name, "HARNESS_ERROR", True, environment, root)
        return [
            Check(name, "PASS", detail)
            for name, detail in (
                ("PreToolUse", "Installed executable captured a baseline"),
                (
                    "PostToolUse",
                    "Comparison, regression blocking and redelivery verified",
                ),
                (
                    "Hook protocol",
                    "Explicit outcomes and event-specific denial verified",
                ),
                (
                    "Runtime smoke",
                    "Temporary project and isolated home; no user commands executed",
                ),
            )
        ]

    def _call(
        self,
        event: dict,
        name: str,
        status: str,
        blocked: bool,
        environment: dict[str, str],
        cwd: Path,
    ) -> None:
        executable = (
            self._installation.pre if name == "PreToolUse" else self._installation.post
        )
        result = subprocess.run(
            [str(executable)],
            input=json.dumps({**event, "hook_event_name": name}),
            text=True,
            check=False,
            capture_output=True,
            env=environment,
            cwd=cwd,
            timeout=120,
        )
        if result.returncode != 0 or protocol_result(result.stdout, name) != (
            status,
            blocked,
        ):
            raise ValueError(
                f"{name} smoke expected {status}; executable/protocol check failed"
            )


class StorageProbe:
    def run(self, root: Path) -> Check:
        existing = root
        while not existing.exists():
            existing = existing.parent
        with tempfile.TemporaryDirectory(
            prefix=".harness-doctor-", dir=existing
        ) as directory:
            file = AtomicFile(Path(directory) / "probe.json")
            file.write_json({"probe": True})
            if file.read_json() != {"probe": True}:
                raise ValueError("State storage readback failed")
        return Check(
            "State storage",
            "PASS",
            f"Atomic write/read in {existing}; isolated smoke also checks locks",
        )
