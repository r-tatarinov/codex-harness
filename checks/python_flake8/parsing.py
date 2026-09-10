"""Compatibility imports for Flake8 metric output parsing."""

from ..analyzers.flake8.parsing import DELIMITER, parse_metric_output

parse_output = parse_metric_output

__all__ = ["DELIMITER", "parse_output"]
