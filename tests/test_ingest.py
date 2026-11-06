import pytest
from engine.fifo import is_long_term
from ingest.tradebook import build_positions, parse_tradebook, reconcile, to_paise

CSV = """symbol,trade_date,trade_type,quantity,price
ABC,2024-01-10,buy,10,100.50
ABC,2025-03-05,buy,10,120
ABC,2025-06-01,sell,12,150
XYZ,2026-02-01,buy,5,2000
XYZ,2026-02-02,sell,8,2100
"""


def test_fifo_replay_leaves_correct_lots():
    lots, last, issues = parse_tradebook(CSV)
    abc = lots["ABC"]
    assert [(l.buy_date.isoformat(), l.qty, l.unit_cost) for l in abc] == [("2025-03-05", 8, 12000)]
    assert "XYZ" not in lots                      # fully sold
    assert any("XYZ" in i and "3 more shares" in i for i in issues)   # oversell flagged, not guessed
    assert last["ABC"] == 15000


def test_positions_flag_last_price_fallback():
    lots, last, _ = parse_tradebook(CSV)
    pos, issues = build_positions(lots, last)
    assert pos[0].price == 15000 and any("last traded price" in i for i in issues)
    pos, issues = build_positions(lots, last, {"ABC": to_paise("160.25")})
    assert pos[0].price == 16025 and not issues


def test_reconcile():
    lots, _, _ = parse_tradebook(CSV)
    assert reconcile(lots, {"ABC": 8}) == []
    assert "tradebook gives 8" in reconcile(lots, {"ABC": 10})[0]


def test_missing_columns_rejected():
    with pytest.raises(ValueError):
        parse_tradebook("symbol,qty\nABC,1\n")


def test_decimal_paise_no_float_error():
    assert to_paise("0.29") == 29 and to_paise("1,234.565") == 123457
