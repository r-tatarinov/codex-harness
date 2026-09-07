from finding import Finding


def build_index(
    findings: list[Finding],
) -> dict[tuple[str, str], Finding]:
    return {finding.key: finding for finding in findings}


def is_regression(
    before: Finding | None,
    after: Finding,
) -> bool:
    if before is None:
        return True

    return after.value > before.value


def find_regressions(
    before: list[Finding],
    after: list[Finding],
) -> list[Finding]:
    before_index = build_index(before)

    regressions: list[Finding] = []

    for finding in after:
        previous = before_index.get(finding.key)

        if is_regression(previous, finding):
            regressions.append(finding)

    return regressions
