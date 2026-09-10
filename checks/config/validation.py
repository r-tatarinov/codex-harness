"""Validate merged Harness configuration and build its typed schema."""

from ..analyzers.configuration import parse_tools
from .schema import ConfigurationError, QualityConfig


def expect_table(value: object, path: str) -> dict:
    if not isinstance(value, dict):
        raise ConfigurationError(f"{path}: expected a TOML table")
    return value


def reject_unknown(table: dict, allowed: set | frozenset, path: str) -> None:
    unknown = set(table) - set(allowed)
    if unknown:
        raise ConfigurationError(f"{path}.{min(unknown)}: unknown parameter")


def positive_integer(value: object, path: str) -> int:
    if type(value) is not int or value < 1:
        raise ConfigurationError(f"{path}: expected an integer >= 1")
    return value


def validate_config(raw: dict) -> QualityConfig:
    reject_unknown(raw, {"schema_version", "verification", "tools"}, "quality")
    if raw.get("schema_version") != 1:
        raise ConfigurationError("schema_version: expected 1")
    verification = expect_table(raw.get("verification"), "verification")
    reject_unknown(verification, {"max_attempts"}, "verification")
    maximum = positive_integer(
        verification.get("max_attempts"), "verification.max_attempts"
    )

    return QualityConfig(maximum, parse_tools(raw.get("tools")))
