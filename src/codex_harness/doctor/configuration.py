import json
import os
import shutil
import tomllib
from pathlib import Path

from ..checks.analyzers.catalog import CONFIGURATIONS
from ..checks.config.defaults import DEFAULT_CONFIG
from ..checks.config.transformations import merge
from ..checks.config.validation import ConfigurationValidator
from .parsing import command_tokens, handler_errors, hook_tables, source_paths
from .schema import Check, Installation


class HookConfigurationInspector:
    def __init__(self, cwd: Path, installation: Installation) -> None:
        self._cwd = cwd
        self._installation = installation
        self._found: dict[str, list[str]] = {"PreToolUse": [], "PostToolUse": []}
        self._errors: list[str] = []
        self._sources: list[str] = []
        self._states: dict[str, dict] = {}
        self._handler_ids: set[str] = set()

    def inspect(self) -> list[Check]:
        home = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))
        for path in source_paths(self._cwd, home):
            try:
                text = path.read_text(encoding="utf-8")
            except FileNotFoundError:
                continue
            except OSError as exc:
                self._errors.append(f"Cannot read {path}: {type(exc).__name__}")
                continue
            self._sources.append(str(path))
            try:
                raw = (
                    json.loads(text) if path.suffix == ".json" else tomllib.loads(text)
                )
                hooks = hook_tables(raw)
                if raw.get("features", {}).get("hooks") is False:
                    self._errors.append(f"Hooks disabled in {path}")
                self._inspect_hooks(hooks, path)
            except (ValueError, TypeError, AttributeError) as exc:
                self._errors.append(f"Invalid configuration {path}: {exc}")
        for key in self._handler_ids:
            if self._states.get(key, {}).get("enabled") is False:
                self._errors.append(f"Disabled Harness hook {key}; inspect /hooks")
        for event, locations in self._found.items():
            if len(locations) != 1:
                self._errors.append(
                    f"{event}: expected one Harness handler, found {len(locations)}"
                )
        return [
            Check(
                "Configuration",
                "FAIL" if self._errors else "PASS",
                (
                    "; ".join(self._errors)
                    if self._errors
                    else "Inspected sources: " + ", ".join(self._sources)
                ),
            ),
            Check(
                "Trust",
                "UNKNOWN",
                "Active-session layers, plugin/managed sources and current hook trust are not confirmed. "
                "Review both Harness definitions and project trust in Codex /hooks; restart after changes.",
            ),
        ]

    def _inspect_hooks(self, hooks: dict, path: Path) -> None:
        for event in self._found:
            groups = hooks.get(event, [])
            if not isinstance(groups, list):
                raise TypeError(f"{event} must be an array")
            for index, group in enumerate(groups):
                if not isinstance(group, dict) or not isinstance(
                    group.get("hooks"), list
                ):
                    raise TypeError(f"Invalid {event} group")
                for handler_index, handler in enumerate(group["hooks"]):
                    if not isinstance(handler, dict):
                        raise TypeError("Invalid hook handler")
                    command = handler.get("command", "")
                    if isinstance(command, str) and any(
                        token in command
                        for token in (
                            "codex-harness",
                            "codex_harness",
                            "hooks/pre_tool.py",
                            "hooks/post_tool.py",
                        )
                    ):
                        location = f"{path}:{event}:{index}:{handler_index}"
                        self._found[event].append(location)
                        wire_event = (
                            "pre_tool_use" if event == "PreToolUse" else "post_tool_use"
                        )
                        self._handler_ids.add(
                            f"{path}:{wire_event}:{index}:{handler_index}"
                        )
                        self._inspect_handler(group, handler, event, location)
        for key, state in hooks.get("state", {}).items():
            if isinstance(state, dict):
                self._states[key] = state

    def _inspect_handler(
        self, group: dict, handler: dict, event: str, location: str
    ) -> None:
        self._errors.extend(
            f"{location}: {error}" for error in handler_errors(group, handler)
        )
        tokens = command_tokens(handler.get("command"))
        expected = (
            self._installation.pre if event == "PreToolUse" else self._installation.post
        )
        resolved = shutil.which(tokens[0]) if len(tokens) == 1 else None
        if resolved is None or Path(resolved).resolve() != expected.resolve():
            self._errors.append(
                f"{location}: replace command with {expected}; direct .py and shell wrappers are unsupported"
            )


class QualityConfigurationInspector:
    def inspect(self, path: Path) -> Check:
        defaults = tomllib.loads(DEFAULT_CONFIG.read_text(encoding="utf-8"))
        try:
            text = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            text = ""
        try:
            settings = ConfigurationValidator(CONFIGURATIONS).validate(
                merge(defaults, tomllib.loads(text))
            )
        except (OSError, ValueError, TypeError, KeyError, RuntimeError) as exc:
            return Check("Quality config", "FAIL", f"{path}: {exc}")
        names = (
            ", ".join(tool.name for tool in settings.enabled_tools)
            or "none (NOT_APPLICABLE)"
        )
        return Check(
            "Quality config",
            "PASS",
            f"Enabled analyzers: {names}; configuration was not modified",
        )
