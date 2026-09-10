"""Schema used to describe one analyzer's configuration surface."""

from collections.abc import Callable
from dataclasses import dataclass

from ..config.schema import ToolConfig


def accept_configuration(config: ToolConfig) -> None:
    """Default validator for analyzers without extra environment constraints."""


@dataclass(frozen=True)
class ToolConfigSpec:
    rule_keys: frozenset[str] = frozenset()
    limit_keys: frozenset[str] = frozenset()
    option_keys: frozenset[str] = frozenset()
    plugin_support: bool = False

    @property
    def keys(self) -> frozenset[str]:
        keys = {"enabled", "use_project_config", "timeout_seconds"}
        keys.update(("rules", "limits", "options"))
        if self.plugin_support:
            keys.add("plugins")
        return frozenset(keys)


@dataclass(frozen=True)
class AnalyzerConfiguration:
    spec: ToolConfigSpec
    validate: Callable[[ToolConfig], None] = accept_configuration
