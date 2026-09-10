import subprocess
import sys
import tempfile
from pathlib import Path

from ...config.schema import ToolConfig
from ..schema import SourceDocument


def run_check(document: SourceDocument, config: ToolConfig) -> str:
    path = document.path.resolve()
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", suffix=path.suffix, delete=False
        ) as file:
            temporary = Path(file.name)
            file.write(document.source)
        command = [
            sys.executable,
            "-m",
            "mypy",
            "--output=json",
            "--show-error-codes",
            "--no-error-summary",
            "--no-pretty",
            "--no-color-output",
            "--no-incremental",
        ]
        if not config.use_project_config:
            command.append("--config-file=")
        for key in ("enable_error_code", "disable_error_code"):
            values = config.rules.get(key, ())
            if values:
                command.extend((f"--{key.replace('_', '-')}", ",".join(values)))
        for name, value in config.options.items():
            flag = f"--{name.replace('_', '-')}"
            if isinstance(value, bool):
                command.append(flag if value else f"--no-{name.replace('_', '-')}")
            else:
                command.extend((flag, str(value)))
        command.extend(("--shadow-file", str(path), str(temporary), str(path)))
        result = subprocess.run(
            command,
            text=True,
            capture_output=True,
            cwd=document.working_directory,
            check=False,
            timeout=config.timeout_seconds,
        )
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    if result.returncode not in (0, 1):
        raise RuntimeError(
            result.stderr.strip()
            or result.stdout.strip()
            or f"MyPy failed with exit code {result.returncode}"
        )
    if result.stderr.strip():
        raise RuntimeError(f"MyPy returned unexpected stderr: {result.stderr.strip()}")
    return result.stdout
