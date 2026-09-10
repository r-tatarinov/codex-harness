"""Load, merge, and expose Harness configuration."""

import os
import tempfile
import tomllib
from pathlib import Path

from . import paths
from .defaults import default_config_text
from .migration import migrate_config
from .schema import ConfigurationError, QualityConfig
from .validation import validate_config


def ensure_config() -> None:
    path = paths.CONFIG_PATH
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, delete=False
        ) as file:
            temporary = Path(file.name)
            file.write(default_config_text())
            file.flush()
            os.fsync(file.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError:
            pass
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def merge(defaults: dict, overrides: dict) -> dict:
    merged = defaults.copy()
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_settings() -> QualityConfig:
    ensure_config()
    path = paths.CONFIG_PATH
    defaults = default_config_text()
    migrate_config(path, defaults)
    try:
        with path.open("rb") as file:
            overrides = tomllib.load(file)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigurationError(f"cannot parse {path}: {exc}") from exc
    return validate_config(merge(tomllib.loads(defaults), overrides))


def load_config() -> dict:
    """Return the validated merged mapping for compatibility with the old API."""
    settings = load_settings()
    return {
        "schema_version": 1,
        "verification": {"max_attempts": settings.max_attempts},
        "tools": {
            name: {
                "enabled": tool.enabled,
                "use_project_config": tool.use_project_config,
                "timeout_seconds": tool.timeout_seconds,
                "plugins": list(tool.plugins),
                "rules": {key: list(value) for key, value in tool.rules.items()},
                "limits": tool.limits.copy(),
                "options": tool.options.copy(),
            }
            for name, tool in settings.tools.items()
        },
    }


def load_max_attempts() -> int:
    return load_settings().max_attempts


def load_max_function_lines() -> int:
    return load_settings().tools["flake8"].limits["CFQ001"]


def load_ruff_settings() -> dict[str, int]:
    limits = load_settings().tools["ruff"].limits
    return {
        "max_complexity": limits["C901"],
        "max_branches": limits["PLR0912"],
        "max_statements": limits["PLR0915"],
        "max_nested_blocks": limits["PLR1702"],
    }
