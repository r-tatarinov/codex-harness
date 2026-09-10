from ...config.schema import ToolConfig
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
