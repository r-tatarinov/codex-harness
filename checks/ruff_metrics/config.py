"""Global Ruff metric limits and the command options enforcing them."""

import tomllib
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parents[2] / "pyproject.toml"
METRIC_SETTINGS = {
    "C901": ("mccabe", "max-complexity"),
    "PLR0912": ("pylint", "max-branches"),
    "PLR1702": ("pylint", "max-nested-blocks"),
}
METRIC_CODES = frozenset(METRIC_SETTINGS)


def load_limits() -> dict[str, int]:
    with CONFIG_PATH.open("rb") as file:
        lint = tomllib.load(file)["tool"]["ruff"]["lint"]

    limits = {}
    for code, (plugin, setting) in METRIC_SETTINGS.items():
        value = lint[plugin][setting]
        if type(value) is not int or value < 0:
            raise ValueError(f"Invalid Harness Ruff limit: {plugin}.{setting}")
        limits[code] = value
    return limits


def build_options(limits: dict[str, int]) -> tuple[str, ...]:
    options = [
        "--isolated",
        "--ignore-noqa",
        "--config",
        "lint.preview=true",
        "--config",
        "lint.explicit-preview-rules=true",
        "--select",
        ",".join(METRIC_SETTINGS),
    ]
    for code, (plugin, setting) in METRIC_SETTINGS.items():
        options.extend(("--config", f"lint.{plugin}.{setting}={limits[code]}"))
    return tuple(options)
