import tomllib

from ..storage import AtomicFile
from .errors import ConfigurationError
from .serialization import dump_config
from .transformations import migrate_legacy_mapping


class ConfigurationMigrator:
    def __init__(self, file: AtomicFile, default_text: str) -> None:
        self._file = file
        self._defaults = default_text

    def migrate(self) -> None:
        path = self._file.path
        try:
            parsed = tomllib.loads(self._file.read_text())
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
        migrated = dump_config(
            migrate_legacy_mapping(parsed, tomllib.loads(self._defaults))
        )
        self._file.backup_to(path.with_name("quality.toml.v0.bak"))
        self._file.write_text(migrated)
