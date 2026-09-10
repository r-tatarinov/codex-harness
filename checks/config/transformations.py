from copy import deepcopy

from .errors import ConfigurationError
from .parsing import expect_table, positive_integer, reject_unknown


def merge(defaults: dict, overrides: dict) -> dict:
    merged = defaults.copy()
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def migrate_legacy_mapping(legacy: dict, defaults: dict) -> dict:
    defaults = deepcopy(defaults)
    unknown = set(legacy) - {"verification", "python"}
    if unknown:
        raise ConfigurationError(f"unknown legacy setting: {min(unknown)}")
    verification = expect_table(legacy.get("verification", {}), "verification")
    python = expect_table(legacy.get("python", {}), "python")
    reject_unknown(verification, {"max_attempts"}, "verification")
    reject_unknown(python, {"functions", "ruff"}, "python")
    functions = expect_table(python.get("functions", {}), "python.functions")
    ruff = expect_table(python.get("ruff", {}), "python.ruff")
    reject_unknown(functions, {"max_lines"}, "python.functions")
    names = {
        "max_complexity": ("C901", 10),
        "max_branches": ("PLR0912", 12),
        "max_statements": ("PLR0915", 50),
        "max_nested_blocks": ("PLR1702", 4),
    }
    reject_unknown(ruff, set(names), "python.ruff")
    defaults["verification"]["max_attempts"] = positive_integer(
        verification.get("max_attempts", 3), "verification.max_attempts"
    )
    defaults["tools"]["flake8"]["limits"]["CFQ001"] = positive_integer(
        functions.get("max_lines", 80), "python.functions.max_lines"
    )
    for old_name, (code, fallback) in names.items():
        defaults["tools"]["ruff"]["limits"][code] = positive_integer(
            ruff.get(old_name, fallback), f"python.ruff.{old_name}"
        )
    return defaults
