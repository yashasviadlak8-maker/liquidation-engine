"""FIFO consumption of lots (s.45(2A), 1961 Act; new-Act section number TBD)."""
import calendar
from dataclasses import dataclass
from datetime import date

from .models import Position


def add_months(d: date, n: int) -> date:
    y, m = divmod(d.month - 1 + n, 12)
    year, month = d.year + y, m + 1
    return date(year, month, min(d.day, calendar.monthrange(year, month)[1]))


def is_long_term(buy: date, sale: date, months: int = 12) -> bool:
    """Long-term iff held for MORE than `months` months."""
    return sale > add_months(buy, months)


@dataclass(frozen=True)
class Consumption:
    lot_index: int   # index in the position's original lot tuple
    qty: int
    gain: int        # paise, may be negative
    long_term: bool


def consume(position: Position, qty: int, sale_date: date, lt_months: int = 12):
    if qty < 0 or qty > position.total_qty:
        raise ValueError(f"cannot sell {qty} of {position.key}: holds {position.total_qty}")
    order = sorted(range(len(position.lots)), key=lambda i: (position.lots[i].buy_date, i))
    out, left = [], qty
    for i in order:
        if left == 0:
            break
        lot = position.lots[i]
        take = min(lot.qty, left)
        out.append(Consumption(
            lot_index=i, qty=take,
            gain=(position.price - lot.unit_cost) * take,
            long_term=is_long_term(lot.buy_date, sale_date, lt_months)))
        left -= take
    return out
