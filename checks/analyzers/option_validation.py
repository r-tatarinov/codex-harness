"""Reusable validation primitives for analyzer option mappings."""

import re
from collections.abc import Iterable

from ..config.schema import ConfigurationError


def validate_types(
    options: dict[str, object],
    *,
    path: str,
    positive: Iterable[str] = (),
    boolean: Iterable[str] = (),
) -> None:
    for key in positive:
        value = options.get(key)
        if value is not None and (type(value) is not int or value < 1):
            raise ConfigurationError(f"{path}.{key}: expected an integer >= 1")
    for key in boolean:
        value = options.get(key)
        if value is not None and type(value) is not bool:
            raise ConfigurationError(f"{path}.{key}: expected boolean")


def validate_pattern(
    options: dict[str, object],
    key: str,
    pattern: str,
    description: str,
    *,
    path: str,
) -> None:
    value = options.get(key)
    values = value if isinstance(value, tuple) else (value,)
    if value is not None and any(
        not isinstance(item, str) or re.fullmatch(pattern, item) is None
        for item in values
    ):
        raise ConfigurationError(f"{path}.{key}: invalid {description}")


def validate_choice(
    options: dict[str, object], key: str, choices: frozenset[str], *, path: str
) -> None:
    value = options.get(key)
    if value is not None and value not in choices:
        raise ConfigurationError(f"{path}.{key}: invalid value")
