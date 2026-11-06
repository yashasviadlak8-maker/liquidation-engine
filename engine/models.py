"""All money is integer paise. No floats anywhere in the engine."""
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Lot:
    buy_date: date
    qty: int
    unit_cost: int  # paise per share (grandfathering already applied by caller)


@dataclass(frozen=True)
class Position:
    """One scrip in one demat account. FIFO is applied per position."""
    account: str
    symbol: str
    price: int  # paise per share
    lots: tuple

    @property
    def key(self):
        return (self.account, self.symbol)

    @property
    def total_qty(self) -> int:
        return sum(l.qty for l in self.lots)
