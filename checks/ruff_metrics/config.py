"""Compatibility API for the former Ruff metric configuration module."""

from ..analyzers.ruff.configuration import METRIC_CODES, METRIC_SETTINGS, metric_options
from ..config import load_ruff_settings

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
    return metric_options(limits)


__all__ = [
    "CONFIG_KEYS",
    "METRIC_CODES",
    "METRIC_SETTINGS",
    "build_options",
    "load_limits",
]
