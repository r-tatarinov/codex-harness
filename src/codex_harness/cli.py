import argparse
import importlib
import json
import subprocess
from dataclasses import asdict
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(prog="codex-harness")
    subcommands = parser.add_subparsers(dest="command", required=True)
    doctor = subcommands.add_parser(
        "doctor", help="Inspect installation and safely exercise both hooks"
    )
    doctor.add_argument("--cwd", type=Path, default=Path.cwd())
    doctor.add_argument("--json", action="store_true")
    arguments = parser.parse_args()
    try:
        if not arguments.cwd.is_dir():
            raise ValueError("--cwd must name an existing project directory")
        service = importlib.import_module("codex_harness.doctor.service")
        presentation = importlib.import_module("codex_harness.doctor.parsing")
        report = service.HarnessDoctor().run(arguments.cwd.resolve())
        output = (
            json.dumps({**asdict(report), "result": report.status})
            if arguments.json
            else presentation.format_report(report)
        )
        print(output)
        return report.exit_code
    except (
        ImportError,
        OSError,
        ValueError,
        TypeError,
        KeyError,
        RuntimeError,
        subprocess.SubprocessError,
    ) as exc:
        reason = f"{type(exc).__name__}: {exc}. Reinstall Harness and check interpreter, configuration and state permissions."
        if arguments.json:
            print(
                json.dumps(
                    {
                        "result": "FAIL",
                        "checks": [
                            {"name": "Doctor", "status": "FAIL", "detail": reason}
                        ],
                    }
                )
            )
        else:
            print(
                f"Codex Harness Doctor\n\nDoctor           FAIL    {reason}\n\nResult: FAIL"
            )
        return 1
