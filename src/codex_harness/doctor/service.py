import subprocess
from pathlib import Path

from .configuration import HookConfigurationInspector, QualityConfigurationInspector
from .installation import InstallationInspector
from .schema import Check, Report
from .smoke import RuntimeSmoke, StorageProbe


class HarnessDoctor:
    def run(self, cwd: Path) -> Report:
        installation, checks = InstallationInspector().inspect()
        checks.extend(HookConfigurationInspector(cwd, installation).inspect())
        checks.append(
            QualityConfigurationInspector().inspect(
                Path.home() / ".codex/harness/config/quality.toml"
            )
        )
        try:
            checks.append(StorageProbe().run(Path.home() / ".codex/harness/state"))
        except (OSError, ValueError) as exc:
            checks.append(
                Check(
                    "State storage",
                    "FAIL",
                    f"{type(exc).__name__}: check storage permissions",
                )
            )
        if any(
            item.status == "FAIL"
            for item in checks
            if item.name in ("Package", "Entry points")
        ):
            checks.append(
                Check("Runtime smoke", "UNKNOWN", "Repair the installed package first")
            )
        else:
            try:
                checks.extend(RuntimeSmoke(installation).run())
            except (
                OSError,
                ValueError,
                TypeError,
                KeyError,
                subprocess.SubprocessError,
            ) as exc:
                checks.append(
                    Check("Runtime smoke", "FAIL", f"{type(exc).__name__}: {exc}")
                )
        return Report(tuple(checks))
