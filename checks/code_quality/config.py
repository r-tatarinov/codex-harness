"""Harness quality configuration and verification retry limit."""

import tomllib
from pathlib import Path

HARNESS_ROOT = Path.home() / ".codex" / "harness"
CONFIG_PATH = HARNESS_ROOT / "config" / "quality.toml"


def load_config() -> dict:
    with CONFIG_PATH.open("rb") as file:
        return tomllib.load(file)


def load_max_attempts() -> int:
    verification = load_config().get("verification", {})
    if not isinstance(verification, dict):
        raise TypeError("verification must be a TOML table")
    value = verification.get("max_attempts", 3)
    if type(value) is not int or value < 1:
        raise ValueError("verification.max_attempts must be an integer >= 1")
    return value
