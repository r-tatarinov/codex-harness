"""Numeric regression policy for Ruff metrics."""

from .finding import Finding


def find_regressions(
    before: list[Finding],
    after: list[Finding],
) -> list[Finding]:
    before_index = {finding.key: finding for finding in before}

    regressions: list[Finding] = []

    for finding in after:
        previous = before_index.get(finding.key)

        if previous is None or finding.value > previous.value:
            regressions.append(finding)

    return regressions
