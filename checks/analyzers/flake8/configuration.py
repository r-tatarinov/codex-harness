"""Configuration schema and plugin validation for Flake8."""

from importlib.metadata import PackageNotFoundError, entry_points, version

from ...config.schema import ConfigurationError, ToolConfig
from ..config_schema import ToolConfigSpec
from ..option_validation import validate_types

SPEC = ToolConfigSpec(
    rule_keys=frozenset({"select", "ignore"}),
    limit_keys=frozenset({"CFQ001"}),
    option_keys=frozenset({"max_line_length", "max_complexity"}),
    plugin_support=True,
)


def validate_configuration(config: ToolConfig) -> None:
    validate_types(
        config.options,
        path="tools.flake8.options",
        positive={"max_line_length", "max_complexity"},
    )
    prefixes = {entry.name for entry in entry_points(group="flake8.extension")}
    for plugin in config.plugins:
        try:
            version(plugin)
        except PackageNotFoundError as exc:
            raise ConfigurationError(
                f"tools.flake8.plugins: required plugin {plugin!r} is not installed"
            ) from exc
    for group, selectors in config.rules.items():
        for selector in selectors:
            if not any(selector.startswith(prefix) for prefix in prefixes):
                raise ConfigurationError(
                    f"tools.flake8.rules.{group}: unknown rule {selector!r}"
                )
