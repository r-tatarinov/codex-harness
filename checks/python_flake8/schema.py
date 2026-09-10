"""Normalized shape of one Flake8 diagnostic."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Flake8Finding:
    code: str
    message: str
    path: str
    line: int
    column: int
