from datetime import date
import pytest
from engine.fifo import add_months, is_long_term, consume
from engine.models import Lot, Position

R = 100  # paise per rupee


def test_holding_period_boundary():
    buy = date(2025, 1, 15)
    assert not is_long_term(buy, date(2026, 1, 15))   # exactly 12 months: still short
    assert is_long_term(buy, date(2026, 1, 16))


def test_leap_day_buy():
    assert add_months(date(2024, 2, 29), 12) == date(2025, 2, 28)
    assert not is_long_term(date(2024, 2, 29), date(2025, 2, 28))
    assert is_long_term(date(2024, 2, 29), date(2025, 3, 1))


def make():
    return Position("A", "XYZ", 200 * R, (
        Lot(date(2026, 6, 1), 10, 150 * R),   # newer, listed first on purpose
        Lot(date(2024, 1, 1), 10, 100 * R),
    ))


def test_fifo_takes_oldest_first_across_lots():
    cs = consume(make(), 15, date(2026, 11, 5))
    assert [(c.lot_index, c.qty) for c in cs] == [(1, 10), (0, 5)]
    assert cs[0].gain == 1000 * R and cs[0].long_term
    assert cs[1].gain == 250 * R and not cs[1].long_term


def test_partial_lot():
    cs = consume(make(), 4, date(2026, 11, 5))
    assert len(cs) == 1 and cs[0].qty == 4 and cs[0].gain == 400 * R


def test_oversell_raises():
    with pytest.raises(ValueError):
        consume(make(), 21, date(2026, 11, 5))
