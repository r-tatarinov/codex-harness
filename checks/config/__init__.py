"""Stable public entry point for Harness configuration."""

from importlib import import_module

from . import paths
from .defaults import DEFAULT_CONFIG
from .paths import CONFIG_PATH, HARNESS_ROOT
from .schema import ConfigurationError, QualityConfig, ToolConfig


def _loader():
    return import_module(f"{__name__}.loader")


def ensure_config() -> None:
    _loader().ensure_config()


def load_config() -> dict:
    return _loader().load_config()


def load_max_attempts() -> int:
    return _loader().load_max_attempts()


def load_max_function_lines() -> int:
    return _loader().load_max_function_lines()


def load_ruff_settings() -> dict[str, int]:
    return _loader().load_ruff_settings()


def load_settings() -> QualityConfig:
    return _loader().load_settings()


__all__ = [
    "CONFIG_PATH",
    "DEFAULT_CONFIG",
    "HARNESS_ROOT",
    "ConfigurationError",
    "QualityConfig",
    "ToolConfig",
    "ensure_config",
    "load_config",
    "load_max_attempts",
    "load_max_function_lines",
    "load_ruff_settings",
    "load_settings",
    "paths",
]
