import subprocess
import sys

from ...config.schema import ToolConfig
from ..schema import SourceDocument


def run_check(document: SourceDocument, config: ToolConfig) -> bool:
    path = document.path.resolve()
    command = [sys.executable, "-m", "black", "--check", "--quiet"]
    if not config.use_project_config:
        command.extend(("--config", "/dev/null"))
    for name, value in config.options.items():
        flag = f"--{name.replace('_', '-')}"
        if isinstance(value, bool):
            command.append(flag if value else f"--no-{name.replace('_', '-')}")
        elif isinstance(value, tuple):
            for item in value:
                command.extend((flag, str(item)))
        else:
            command.extend((flag, str(value)))
    command.extend(("--stdin-filename", str(path), "-"))
    result = subprocess.run(
        command,
        input=document.source,
        text=True,
        capture_output=True,
        cwd=document.working_directory,
        check=False,
        timeout=config.timeout_seconds,
    )
    if result.returncode not in (0, 1):
        raise RuntimeError(
            result.stderr.strip() or f"Black failed with exit code {result.returncode}"
        )
    return result.returncode == 1
