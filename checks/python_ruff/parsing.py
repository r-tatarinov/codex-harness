"""Compatibility imports for Ruff output parsing."""

from ..analyzers.ruff.parsing import parse_diagnostic, parse_output

__all__ = ["parse_diagnostic", "parse_output"]
