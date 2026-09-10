from importlib.metadata import PackageNotFoundError, entry_points, version

from ...config.errors import ConfigurationError
from ...config.schema import ToolConfig


class Flake8PluginPolicy:

    def validate(self, config: ToolConfig) -> None:
        prefixes = {entry.name for entry in entry_points(group="flake8.extension")}
        for plugin in config.plugins:
            try:
                version(plugin)
            except PackageNotFoundError as exc:
                raise ConfigurationError(
                    f"tools.flake8.plugins: required plugin {plugin!r} is not installed"
                ) from exc
        for group, selectors in config.rules.items():
            for selector in selectors:
                if not any(selector.startswith(prefix) for prefix in prefixes):
                    raise ConfigurationError(
                        f"tools.flake8.rules.{group}: unknown rule {selector!r}"
                    )
