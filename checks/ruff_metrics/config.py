"""Global Ruff metric limits and the command options enforcing them."""

from ..code_quality.config import load_ruff_settings

METRIC_SETTINGS = {
    "C901": ("mccabe", "max-complexity"),
    "PLR0912": ("pylint", "max-branches"),
    "PLR0915": ("pylint", "max-statements"),
    "PLR1702": ("pylint", "max-nested-blocks"),
}
METRIC_CODES = frozenset(METRIC_SETTINGS)
CONFIG_KEYS = {
    "C901": "max_complexity",
    "PLR0912": "max_branches",
    "PLR0915": "max_statements",
    "PLR1702": "max_nested_blocks",
}


def load_limits() -> dict[str, int]:
    settings = load_ruff_settings()
    return {code: settings[key] for code, key in CONFIG_KEYS.items()}


def build_options(limits: dict[str, int]) -> tuple[str, ...]:
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
    return tuple(options)
