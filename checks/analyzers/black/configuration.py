from ...config.schema import ToolConfig
from ..config_schema import ToolConfigSpec
from ..option_validation import validate_pattern, validate_types

SPEC = ToolConfigSpec(
    option_keys=frozenset(
        {
            "line_length",
            "target_version",
            "skip_string_normalization",
            "skip_magic_trailing_comma",
            "preview",
            "unstable",
        }
    )
)


def validate_configuration(config: ToolConfig) -> None:
    validate_types(
        config.options,
        path="tools.black.options",
        positive={"line_length"},
        boolean={
            "skip_string_normalization",
            "skip_magic_trailing_comma",
            "preview",
            "unstable",
        },
    )
    validate_pattern(
        config.options,
        "target_version",
        r"py3\d+",
        "Python target",
        path="tools.black.options",
    )
