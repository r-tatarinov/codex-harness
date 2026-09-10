from .base import AnalyzerAdapter
from .black.adapter import BlackAdapter
from .flake8.adapter import Flake8Adapter
from .mypy.adapter import MypyAdapter
from .pylint.adapter import PylintAdapter
from .ruff.adapter import RuffAdapter

BUILTIN_ANALYZERS: tuple[type[AnalyzerAdapter], ...] = (
    RuffAdapter,
    Flake8Adapter,
    PylintAdapter,
    BlackAdapter,
    MypyAdapter,
)
