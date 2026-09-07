#!/usr/bin/env python3

import ast
import sys
import tomllib
from pathlib import Path

from finding import Finding
from ruff_metrics import check as check_ruff_metrics
from rules.function_length import check as check_function_length
from symbols import build_symbol_index

HARNESS_ROOT = Path.home() / ".codex" / "harness"
CONFIG_PATH = HARNESS_ROOT / "config" / "quality.toml"


def load_config() -> dict:
    with CONFIG_PATH.open("rb") as file:
        return tomllib.load(file)


def analyze_source(
    source: str,
    path: Path,
    config: dict,
) -> list[Finding]:
    tree = ast.parse(
        source,
        filename=str(path),
    )

    symbols = build_symbol_index(tree)
    function_config = config["python"]["functions"]

    findings: list[Finding] = []

    findings.extend(
        check_function_length(
            tree=tree,
            path=path,
            max_lines=function_config["max_lines"],
            symbols=symbols,
        )
    )

    findings.extend(
        check_ruff_metrics(
            source=source,
            tree=tree,
            path=path,
            symbols=symbols,
        )
    )

    return findings


def analyze_file(
    path: Path,
    config: dict,
) -> list[Finding]:
    source = path.read_text(encoding="utf-8")

    return analyze_source(
        source=source,
        path=path,
        config=config,
    )


def print_findings(findings: list[Finding]) -> None:
    print("CODE QUALITY CHECK FAILED")

    for finding in findings:
        print(f"- {finding.path}:{finding.line}: {finding.message}")


def get_python_files(arguments: list[str]) -> list[Path]:
    return [Path(argument) for argument in arguments if Path(argument).suffix == ".py"]


def main() -> int:
    config = load_config()
    python_files = get_python_files(sys.argv[1:])

    findings: list[Finding] = []

    for path in python_files:
        if not path.is_file():
            continue

        try:
            findings.extend(
                analyze_file(
                    path=path,
                    config=config,
                )
            )
        except (
            OSError,
            SyntaxError,
            TypeError,
            ValueError,
            KeyError,
            RuntimeError,
        ) as exc:
            print(
                f"{path}: cannot analyze file: {exc}",
                file=sys.stderr,
            )
            return 1

    if not findings:
        return 0

    print_findings(findings)

    return 1


if __name__ == "__main__":
    sys.exit(main())
