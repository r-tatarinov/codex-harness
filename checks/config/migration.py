"""Detect and migrate the pre-v1 Harness configuration."""

import os
import tempfile
import tomllib
from pathlib import Path

from .schema import ConfigurationError
from .serialization import dump_config
from .validation import expect_table, positive_integer, reject_unknown


def migrate_legacy_mapping(legacy: dict, defaults: dict) -> dict:
    unknown = set(legacy) - {"verification", "python"}
    if unknown:
        raise ConfigurationError(f"unknown legacy setting: {min(unknown)}")
    verification = expect_table(legacy.get("verification", {}), "verification")
    python = expect_table(legacy.get("python", {}), "python")
    reject_unknown(verification, {"max_attempts"}, "verification")
    reject_unknown(python, {"functions", "ruff"}, "python")
    functions = expect_table(python.get("functions", {}), "python.functions")
    ruff = expect_table(python.get("ruff", {}), "python.ruff")
    reject_unknown(functions, {"max_lines"}, "python.functions")
    names = {
        "max_complexity": ("C901", 10),
        "max_branches": ("PLR0912", 12),
        "max_statements": ("PLR0915", 50),
        "max_nested_blocks": ("PLR1702", 4),
    }
    reject_unknown(ruff, set(names), "python.ruff")
    defaults["verification"]["max_attempts"] = positive_integer(
        verification.get("max_attempts", 3), "verification.max_attempts"
    )
    defaults["tools"]["flake8"]["limits"]["CFQ001"] = positive_integer(
        functions.get("max_lines", 80), "python.functions.max_lines"
    )
    for old_name, (code, fallback) in names.items():
        defaults["tools"]["ruff"]["limits"][code] = positive_integer(
            ruff.get(old_name, fallback), f"python.ruff.{old_name}"
        )
    return defaults


def migrate_config(path: Path, default_text: str) -> None:
    try:
        raw = path.read_text(encoding="utf-8")
        parsed = tomllib.loads(raw)
    except (UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise ConfigurationError(f"cannot parse {path}: {exc}") from exc
    if "schema_version" in parsed or "tools" in parsed:
        if "python" in parsed:
            raise ConfigurationError(
                "quality.toml mixes legacy [python.*] and versioned [tools.*] settings"
            )
        return
    if "python" not in parsed:
        return

    migrated = dump_config(migrate_legacy_mapping(parsed, tomllib.loads(default_text)))
    backup = path.with_name("quality.toml.v0.bak")
    try:
        os.link(path, backup)
    except FileExistsError:
        pass
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, delete=False
        ) as file:
            temporary = Path(file.name)
            file.write(migrated)
            file.flush()
            os.fsync(file.fileno())
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
