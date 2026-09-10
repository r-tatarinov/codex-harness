from ...config.schema import ToolConfig
from ..config_schema import ToolConfigSpec
from ..option_validation import validate_pattern, validate_types

SPEC = ToolConfigSpec(
    rule_keys=frozenset({"enable", "disable"}),
    option_keys=frozenset(
        {
            "py_version",
            "max_line_length",
            "max_args",
            "max_branches",
            "max_statements",
            "max_nested_blocks",
        }
    ),
)


def validate_configuration(config: ToolConfig) -> None:
    validate_types(
        config.options,
        path="tools.pylint.options",
        positive={
            "max_line_length",
            "max_args",
            "max_branches",
            "max_statements",
            "max_nested_blocks",
        },
    )
    validate_pattern(
        config.options,
        "py_version",
        r"3\.\d+",
        "Python version",
        path="tools.pylint.options",
    )
