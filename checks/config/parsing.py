from .errors import ConfigurationError


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
