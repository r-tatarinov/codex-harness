from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Finding:
    rule: str
    path: str
    symbol: str
    line: int
    value: int
    limit: int
    message: str

    @property
    def key(self) -> tuple[str, str]:
        return self.rule, self.symbol

    def to_dict(self) -> dict:
        return asdict(self)
