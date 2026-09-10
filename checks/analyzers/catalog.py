from .black.configuration import SPEC as BLACK
from .black.configuration import validate_configuration as validate_black
from .config_schema import AnalyzerConfiguration
from .flake8.configuration import SPEC as FLAKE8
from .flake8.configuration import validate_configuration as validate_flake8
from .flake8.plugin_policy import Flake8PluginPolicy
from .mypy.configuration import SPEC as MYPY
from .mypy.configuration import validate_configuration as validate_mypy
from .pylint.configuration import SPEC as PYLINT
from .pylint.configuration import validate_configuration as validate_pylint
from .ruff.configuration import SPEC as RUFF
from .ruff.configuration import validate_configuration as validate_ruff

CONFIGURATIONS = {
    "ruff": AnalyzerConfiguration(RUFF, validate_ruff),
    "flake8": AnalyzerConfiguration(FLAKE8, validate_flake8, Flake8PluginPolicy()),
    "pylint": AnalyzerConfiguration(PYLINT, validate_pylint),
    "black": AnalyzerConfiguration(BLACK, validate_black),
    "mypy": AnalyzerConfiguration(MYPY, validate_mypy),
}
