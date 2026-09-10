import re

from ..config.errors import ConfigurationError
from ..config.parsing import expect_table, positive_integer, reject_unknown
from ..config.schema import ToolConfig
from .config_schema import ToolConfigSpec

RULE_RE = re.compile(r"^(?:[A-Z][A-Z0-9]*\d*|[a-z][a-z0-9-]*)$")


def _string_list(value: object, path: str, *, rules: bool = False) -> tuple[str, ...]:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item for item in value
    ):
        raise ConfigurationError(f"{path}: expected a list of non-empty strings")
    if rules:
        for item in value:
            if RULE_RE.fullmatch(item) is None:
                raise ConfigurationError(f"{path}: invalid rule {item!r}")
    if len(set(value)) != len(value):
        raise ConfigurationError(f"{path}: duplicate values are not allowed")
    return tuple(value)


def _option_value(value: object, path: str) -> object:
    if isinstance(value, bool) or type(value) is int or isinstance(value, str):
        return value
    if isinstance(value, list) and all(
        isinstance(item, str) or type(item) is int for item in value
    ):
        return tuple(value)
    raise ConfigurationError(f"{path}: expected a scalar or a list of scalars")


def parse_tool(name: str, raw: object, spec: ToolConfigSpec) -> ToolConfig:
    path = f"tools.{name}"
    table = expect_table(raw, path)
    reject_unknown(table, spec.keys, path)
    enabled = table.get("enabled")
    project = table.get("use_project_config")
    if type(enabled) is not bool:
        raise ConfigurationError(f"{path}.enabled: expected boolean")
    if type(project) is not bool:
        raise ConfigurationError(f"{path}.use_project_config: expected boolean")
    timeout = positive_integer(table.get("timeout_seconds"), f"{path}.timeout_seconds")
    plugins = _string_list(table.get("plugins", []), f"{path}.plugins")
    rules_table = expect_table(table.get("rules", {}), f"{path}.rules")
    reject_unknown(rules_table, spec.rule_keys, f"{path}.rules")
    rules = {
        key: _string_list(value, f"{path}.rules.{key}", rules=True)
        for key, value in rules_table.items()
    }
    limits_table = expect_table(table.get("limits", {}), f"{path}.limits")
    reject_unknown(limits_table, spec.limit_keys, f"{path}.limits")
    limits = {
        key: positive_integer(value, f"{path}.limits.{key}")
        for key, value in limits_table.items()
    }
    options_table = expect_table(table.get("options", {}), f"{path}.options")
    reject_unknown(options_table, spec.option_keys, f"{path}.options")
    options = {
        key: _option_value(value, f"{path}.options.{key}")
        for key, value in options_table.items()
    }
    return ToolConfig(name, enabled, project, timeout, plugins, rules, limits, options)
