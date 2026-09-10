"""Compatibility imports for the Ruff command-line entry point."""

from ..analyzers.ruff.cli import main, print_findings

__all__ = ["main", "print_findings"]
