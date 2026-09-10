"""Stable public entry point for the Black analyzer."""

from importlib import import_module

_EXPORTS = {
    "ADAPTER": ("adapter", "ADAPTER"),
    "BlackAdapter": ("adapter", "BlackAdapter"),
    "SPEC": ("configuration", "SPEC"),
    "validate_configuration": ("configuration", "validate_configuration"),
    "run_check": ("runner", "run_check"),
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
