"""User configuration, defaults, and validated Harness limits."""

import os
import tempfile
import tomllib
from importlib import resources
from pathlib import Path

HARNESS_ROOT = Path.home() / ".codex" / "harness"
CONFIG_PATH = HARNESS_ROOT / "config" / "quality.toml"
DEFAULT_CONFIG = resources.files("codex_harness").joinpath("defaults", "quality.toml")


def _default_config_text() -> str:
    return DEFAULT_CONFIG.read_text(encoding="utf-8")


def ensure_config() -> None:
    if CONFIG_PATH.exists():
        return
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=CONFIG_PATH.parent,
            delete=False,
        ) as file:
            temporary = Path(file.name)
            file.write(_default_config_text())
            file.flush()
            os.fsync(file.fileno())
        try:
            os.link(temporary, CONFIG_PATH)
        except FileExistsError:
            # Another hook initialized the shared configuration first.
            pass
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _merge(defaults: dict, overrides: dict) -> dict:
    merged = defaults.copy()
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_config() -> dict:
    ensure_config()
    defaults = tomllib.loads(_default_config_text())
    with CONFIG_PATH.open("rb") as file:
        overrides = tomllib.load(file)
    return _merge(defaults, overrides)


def _table(config: dict, *path: str) -> dict:
    value: object = config
    for name in path:
        if not isinstance(value, dict):
            raise TypeError(f"{'.'.join(path)} must be a TOML table")
        value = value.get(name)
    if not isinstance(value, dict):
        raise TypeError(f"{'.'.join(path)} must be a TOML table")
    return value


def _positive_integer(table: dict, key: str, qualified_name: str) -> int:
    value = table.get(key)
    if type(value) is not int or value < 1:
        raise ValueError(f"{qualified_name} must be an integer >= 1")
    return value


def load_max_attempts() -> int:
    verification = _table(load_config(), "verification")
    return _positive_integer(
        verification,
        "max_attempts",
        "verification.max_attempts",
    )


def load_max_function_lines() -> int:
    functions = _table(load_config(), "python", "functions")
    return _positive_integer(
        functions,
        "max_lines",
        "python.functions.max_lines",
    )


def load_ruff_settings() -> dict[str, int]:
    ruff = _table(load_config(), "python", "ruff")
    names = (
        "max_complexity",
        "max_branches",
        "max_statements",
        "max_nested_blocks",
    )
    return {
        name: _positive_integer(ruff, name, f"python.ruff.{name}") for name in names
    }
