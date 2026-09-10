from collections import Counter
from collections.abc import Sequence

from .analyzers.schema import ToolFinding


class DefaultRegressionPolicy:

    def compare(
        self, before: Sequence[ToolFinding], after: Sequence[ToolFinding]
    ) -> list[ToolFinding]:
        occurrences = Counter(
            finding.occurrence_key
            for finding in before
            if finding.comparison == "occurrence"
        )
        metrics = {
            finding.metric_key: finding.value
            for finding in before
            if finding.comparison == "metric"
        }
        regressions: list[ToolFinding] = []
        for finding in after:
            if finding.comparison == "metric":
                previous = metrics.get(finding.metric_key)
                assert finding.value is not None
                if previous is None or finding.value > previous:
                    regressions.append(finding)
            elif occurrences[finding.occurrence_key] > 0:
                occurrences[finding.occurrence_key] -= 1
            else:
                regressions.append(finding)
        return regressions
