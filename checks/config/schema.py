from dataclasses import dataclass


@dataclass(frozen=True)
class ToolConfig:
    name: str
    enabled: bool
    use_project_config: bool
    timeout_seconds: int
    plugins: tuple[str, ...]
    rules: dict[str, tuple[str, ...]]
    limits: dict[str, int]
    options: dict[str, object]


@dataclass(frozen=True)
class QualityConfig:
    max_attempts: int
    tools: dict[str, ToolConfig]

    @property
    def enabled_tools(self) -> tuple[ToolConfig, ...]:
        return tuple(tool for tool in self.tools.values() if tool.enabled)
