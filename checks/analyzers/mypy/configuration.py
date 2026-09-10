from ...config.schema import ToolConfig
from ..config_schema import ToolConfigSpec
from ..option_validation import validate_choice, validate_pattern, validate_types

SPEC = ToolConfigSpec(
    rule_keys=frozenset({"enable_error_code", "disable_error_code"}),
    option_keys=frozenset(
        {
            "python_version",
            "strict",
            "check_untyped_defs",
            "disallow_untyped_defs",
            "disallow_incomplete_defs",
            "warn_return_any",
            "warn_unused_ignores",
            "ignore_missing_imports",
            "follow_imports",
        }
    ),
)


def validate_configuration(config: ToolConfig) -> None:
    validate_types(
        config.options,
        path="tools.mypy.options",
        boolean={
            "strict",
            "check_untyped_defs",
            "disallow_untyped_defs",
            "disallow_incomplete_defs",
            "warn_return_any",
            "warn_unused_ignores",
            "ignore_missing_imports",
        },
    )
    validate_pattern(
        config.options,
        "python_version",
        r"3\.\d+",
        "Python version",
        path="tools.mypy.options",
    )
    validate_choice(
        config.options,
        "follow_imports",
        frozenset({"normal", "silent", "skip", "error"}),
        path="tools.mypy.options",
    )
