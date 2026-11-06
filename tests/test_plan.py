from datetime import date
from engine.models import Lot, Position
from engine.plan import evaluate_plan
from engine.tax import TaxProfile

R = 100


def test_end_to_end_mixed_lots(rules):
    pos = Position("A", "XYZ", 200 * R, (
        Lot(date(2024, 1, 1), 10, 100 * R),
        Lot(date(2026, 6, 1), 10, 150 * R),
    ))
    ev = evaluate_plan([pos], {("A", "XYZ"): 15}, date(2026, 11, 5), TaxProfile(), rules)
    assert ev.proceeds == 3000 * R
    assert ev.lt_gain == 1000 * R and ev.st_gain == 250 * R
    assert ev.tax == 52 * R   # 250 * 20% * 1.04 = 52; LT inside exemption
