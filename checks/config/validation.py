from collections.abc import Mapping

from ..analyzers.config_schema import AnalyzerConfiguration
from ..analyzers.configuration import parse_tool
from .errors import ConfigurationError
from .parsing import expect_table, positive_integer, reject_unknown
from .schema import QualityConfig, ToolConfig


class ConfigurationValidator:
    def __init__(self, configurations: Mapping[str, AnalyzerConfiguration]) -> None:
        self._configurations = configurations

    def validate(self, raw: dict) -> QualityConfig:
        reject_unknown(raw, {"schema_version", "verification", "tools"}, "quality")
        if raw.get("schema_version") != 1:
            raise ConfigurationError("schema_version: expected 1")
        verification = expect_table(raw.get("verification"), "verification")
        reject_unknown(verification, {"max_attempts"}, "verification")
        maximum = positive_integer(
            verification.get("max_attempts"), "verification.max_attempts"
        )

        return QualityConfig(maximum, self._tools(raw.get("tools")))

    def _tools(self, raw: object) -> dict[str, ToolConfig]:
        tools = expect_table(raw, "tools")
        unknown = set(tools) - set(self._configurations)
        if unknown:
            raise ConfigurationError(f"tools.{min(unknown)}: unknown tool")
        missing = set(self._configurations) - set(tools)
        if missing:
            raise ConfigurationError(
                f"tools.{min(missing)}: missing tool configuration"
            )
        parsed = {
            name: parse_tool(name, tools[name], definition.spec)
            for name, definition in self._configurations.items()
        }
        for name, definition in self._configurations.items():
            definition.validate(parsed[name])
            if definition.environment_policy is not None:
                definition.environment_policy.validate(parsed[name])
        return parsed
