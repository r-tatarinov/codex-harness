"""Shared source and configuration fixtures."""

from pathlib import Path

from codex_harness.checks.code_quality import config


def function_source(length: int, name: str = "sample") -> str:
    lines = [f"def {name}():", "    values = ["]
    lines.extend(f"        {value}," for value in range(1, length - 2))
    lines.append("    ]")
    lines.append("    return values")
    return "\n".join(lines) + "\n"


class TemporaryConfigMixin:
    temporary_config: Path
    original_config: Path

    def use_config(self, path: Path) -> None:
        self.original_config = config.CONFIG_PATH
        self.temporary_config = path
        config.CONFIG_PATH = path
        self.addCleanup(setattr, config, "CONFIG_PATH", self.original_config)
