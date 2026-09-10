"""Filesystem locations used by Harness configuration."""

from pathlib import Path

HARNESS_ROOT = Path.home() / ".codex" / "harness"
CONFIG_PATH = HARNESS_ROOT / "config" / "quality.toml"
