"""Compatibility imports for the isolated Flake8 metric pass."""

from ..analyzers.flake8.parsing import OUTPUT_FORMAT
from ..analyzers.flake8.runner import FLAKE8_COMMAND, run_metric_check

run_check = run_metric_check

__all__ = ["FLAKE8_COMMAND", "OUTPUT_FORMAT", "run_check"]
