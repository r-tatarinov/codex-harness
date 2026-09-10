"""Stable public entry point for the Flake8 analyzer."""

from importlib import import_module

_EXPORTS = {
    "ADAPTER": ("adapter", "ADAPTER"),
    "Flake8Adapter": ("adapter", "Flake8Adapter"),
    "SPEC": ("configuration", "SPEC"),
    "validate_configuration": ("configuration", "validate_configuration"),
    "DELIMITER": ("parsing", "DELIMITER"),
    "OUTPUT_FORMAT": ("parsing", "OUTPUT_FORMAT"),
    "parse_metric_output": ("parsing", "parse_metric_output"),
    "parse_regular_output": ("parsing", "parse_regular_output"),
    "FLAKE8_COMMAND": ("runner", "FLAKE8_COMMAND"),
    "run_metric_check": ("runner", "run_metric_check"),
    "run_regular_check": ("runner", "run_regular_check"),
    "Flake8Finding": ("schema", "Flake8Finding"),
}
__all__ = list(_EXPORTS)


def __getattr__(name: str):
    try:
        module_name, attribute = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(name) from exc
    value = getattr(import_module(f"{__name__}.{module_name}"), attribute)
    globals()[name] = value
    return value
