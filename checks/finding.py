from dataclasses import dataclass


@dataclass(frozen=True)
class Finding:
    rule: str
    path: str
    symbol: str
    line: int
    value: int
    message: str

    @property
    def key(self) -> tuple[str, str]:
        return self.rule, self.symbol
