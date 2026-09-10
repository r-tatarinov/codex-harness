"""Analyzer-neutral before/after regression comparison."""

from collections import Counter

from .schema import ToolFinding


def find_regressions(
    before: list[ToolFinding], after: list[ToolFinding]
) -> list[ToolFinding]:
    ordinary_before = Counter(
        finding.occurrence_key
        for finding in before
        if finding.comparison == "occurrence"
    )
    metrics_before = {
        finding.metric_key: finding
        for finding in before
        if finding.comparison == "metric"
    }
    regressions: list[ToolFinding] = []
    for finding in after:
        if finding.comparison == "metric":
            previous = metrics_before.get(finding.metric_key)
            if previous is None or finding.value > previous.value:
                regressions.append(finding)
            continue
        if ordinary_before[finding.occurrence_key] > 0:
            ordinary_before[finding.occurrence_key] -= 1
        else:
            regressions.append(finding)
    return regressions
