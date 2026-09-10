"""Configuration schema supported by the Ruff adapter."""

from ...config.schema import ToolConfig
from ..config_schema import ToolConfigSpec
from ..option_validation import validate_pattern, validate_types

METRIC_SETTINGS = {
    "C901": ("mccabe", "max-complexity"),
    "PLR0912": ("pylint", "max-branches"),
    "PLR0915": ("pylint", "max-statements"),
    "PLR1702": ("pylint", "max-nested-blocks"),
}
METRIC_CODES = frozenset(METRIC_SETTINGS)

SPEC = ToolConfigSpec(
    rule_keys=frozenset({"select", "extend_select", "ignore"}),
    limit_keys=frozenset({"C901", "PLR0912", "PLR0915", "PLR1702"}),
    option_keys=frozenset(
        {"target_version", "line_length", "preview", "explicit_preview_rules"}
    ),
)


def validate_configuration(config: ToolConfig) -> None:
    validate_types(
        config.options,
        path="tools.ruff.options",
        positive={"line_length"},
        boolean={"preview", "explicit_preview_rules"},
    )
    validate_pattern(
        config.options,
        "target_version",
        r"py3\d+",
        "Python target",
        path="tools.ruff.options",
    )


def build_regular_options(config: ToolConfig) -> tuple[str, ...]:
    options: list[str] = []
    if not config.use_project_config:
        options.append("--isolated")
    for key in ("select", "extend_select", "ignore"):
        values = config.rules.get(key, ())
        if values:
            options.extend((f"--{key.replace('_', '-')}", ",".join(values)))
    target = config.options.get("target_version")
    if target is not None:
        options.extend(("--target-version", str(target)))
    line_length = config.options.get("line_length")
    if line_length is not None:
        options.extend(("--line-length", str(line_length)))
    preview = config.options.get("preview")
    if preview is not None:
        options.append("--preview" if preview else "--no-preview")
    explicit = config.options.get("explicit_preview_rules")
    if explicit is not None:
        options.extend(
            ("--config", f"lint.explicit-preview-rules={str(explicit).lower()}")
        )
    return tuple(options)


def build_metric_options(config: ToolConfig) -> tuple[str, ...]:
    target = config.options.get("target_version")
    return metric_options(config.limits, str(target) if target is not None else None)


def metric_options(
    limits: dict[str, int], target: str | None = None
) -> tuple[str, ...]:
    options = [
        "--isolated",
        "--ignore-noqa",
        "--config",
        "lint.preview=true",
        "--config",
        "lint.explicit-preview-rules=true",
        "--select",
        ",".join(METRIC_SETTINGS),
    ]
    for code, (plugin, setting) in METRIC_SETTINGS.items():
        options.extend(("--config", f"lint.{plugin}.{setting}={limits[code]}"))
    if target is not None:
        options.extend(("--target-version", target))
    return tuple(options)
