"""Stable public entry point for the Ruff analyzer."""

from importlib import import_module

_EXPORTS = {
    "ADAPTER": ("adapter", "ADAPTER"),
    "RuffAdapter": ("adapter", "RuffAdapter"),
    "SPEC": ("configuration", "SPEC"),
    "validate_configuration": ("configuration", "validate_configuration"),
    "parse_diagnostic": ("parsing", "parse_diagnostic"),
    "parse_output": ("parsing", "parse_output"),
    "RUFF_COMMAND": ("runner", "RUFF_COMMAND"),
    "analyze_file": ("runner", "analyze_file"),
    "analyze_source": ("runner", "analyze_source"),
    "run_check": ("runner", "run_check"),
    "RuffFinding": ("schema", "RuffFinding"),
    "main": ("cli", "main"),
    "print_findings": ("cli", "print_findings"),
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
