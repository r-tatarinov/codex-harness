"""Access to the packaged default configuration."""

from importlib import resources

DEFAULT_CONFIG = resources.files("codex_harness").joinpath("defaults", "quality.toml")


def default_config_text() -> str:
    return DEFAULT_CONFIG.read_text(encoding="utf-8")
