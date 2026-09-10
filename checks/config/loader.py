import tomllib
from pathlib import Path

from ..analyzers.catalog import CONFIGURATIONS
from ..storage import AtomicFile
from .defaults import DEFAULT_CONFIG
from .errors import ConfigurationError
from .migration import ConfigurationMigrator
from .schema import QualityConfig
from .transformations import merge
from .validation import ConfigurationValidator


class ConfigurationLoader:
    def __init__(
        self,
        path: Path,
        default_text: str | None = None,
        validator: ConfigurationValidator | None = None,
    ) -> None:
        self._file = AtomicFile(path)
        self._validator = validator or ConfigurationValidator(CONFIGURATIONS)
        self._defaults = (
            DEFAULT_CONFIG.read_text(encoding="utf-8")
            if default_text is None
            else default_text
        )
        self._migrator = ConfigurationMigrator(self._file, self._defaults)

    def load(self) -> QualityConfig:
        self._file.path.parent.mkdir(parents=True, exist_ok=True)
        if not self._file.path.exists():
            self._file.write_text(self._defaults, exclusive=True)
        self._migrator.migrate()
        try:
            overrides = tomllib.loads(self._file.read_text())
        except tomllib.TOMLDecodeError as exc:
            raise ConfigurationError(f"cannot parse {self._file.path}: {exc}") from exc
        return self._validator.validate(merge(tomllib.loads(self._defaults), overrides))
