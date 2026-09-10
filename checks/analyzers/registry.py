"""Runtime registry of built-in analyzer adapters."""

from .base import AnalyzerAdapter
from .black import ADAPTER as BLACK
from .flake8 import ADAPTER as FLAKE8
from .mypy import ADAPTER as MYPY
from .pylint import ADAPTER as PYLINT
from .ruff import ADAPTER as RUFF

ADAPTERS: dict[str, AnalyzerAdapter] = {
    adapter.name: adapter for adapter in (RUFF, FLAKE8, PYLINT, BLACK, MYPY)
}


def get_adapter(name: str) -> AnalyzerAdapter:
    try:
        return ADAPTERS[name]
    except KeyError as exc:
        raise ValueError(f"Unknown analyzer adapter: {name}") from exc
