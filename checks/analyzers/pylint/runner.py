import subprocess
import sys

from ...config.schema import ToolConfig
from ..schema import SourceDocument


def run_check(document: SourceDocument, config: ToolConfig) -> str:
    path = document.path.resolve()
    command = [
        sys.executable,
        "-m",
        "pylint",
        "--output-format=json2",
        "--reports=n",
        "--score=n",
        "--persistent=n",
        "--from-stdin",
    ]
    if not config.use_project_config:
        command.append("--rcfile=/dev/null")
    for key in ("enable", "disable"):
        values = config.rules.get(key, ())
        if values:
            command.append(f"--{key}={','.join(values)}")
    for name, value in config.options.items():
        rendered = "y" if value is True else "n" if value is False else value
        command.append(f"--{name.replace('_', '-')}={rendered}")
    command.append(str(path))
    result = subprocess.run(
        command,
        input=document.source,
        text=True,
        capture_output=True,
        cwd=document.working_directory,
        check=False,
        timeout=config.timeout_seconds,
    )
    if result.returncode < 0 or result.returncode >= 32:
        raise RuntimeError(
            result.stderr.strip() or f"Pylint failed with exit code {result.returncode}"
        )
    if result.stderr.strip():
        raise RuntimeError(
            f"Pylint returned unexpected stderr: {result.stderr.strip()}"
        )
    return result.stdout
