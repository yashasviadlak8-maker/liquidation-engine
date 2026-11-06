import random
from datetime import date
import pytest
from engine.baselines import pro_rata, largest_first, greedy_tax_aware
from engine.bruteforce import brute_force
from engine.instances import generate_portfolio
from engine.models import Lot, Position
from engine.plan import evaluate_plan
from engine.tax import TaxProfile

R = 100
SALE = date(2026, 11, 5)
P0 = TaxProfile()


def hand_case():
    buy = date(2026, 6, 1)   # short-term on SALE
    c = Position("A", "C", 1000 * R, (Lot(buy, 300, 500 * R),))    # gain 500/share
    d = Position("A", "D", 1000 * R, (Lot(buy, 100, 1500 * R),))   # loss 500/share
    return [c, d]


def test_hand_case_optimum_is_zero_tax(rules):
    pos = hand_case()
    sol = brute_force(pos, 200000 * R, SALE, P0, rules)
    assert sol.tax == 0 and sol.proceeds == 200000 * R
    assert sol.quantities == {("A", "C"): 100, ("A", "D"): 100}


def test_hand_case_pro_rata_pays_tax(rules):
    pos = hand_case()
    x = pro_rata(pos, 200000 * R)
    assert x == {("A", "C"): 150, ("A", "D"): 50}
    # net ST = 75,000 - 25,000 = 50,000 -> 10,000 * 1.04 = 10,400
    assert evaluate_plan(pos, x, SALE, P0, rules).tax == 10400 * R


@pytest.mark.parametrize("seed", range(40))
def test_baselines_feasible_and_never_beat_optimum(rules, seed):
    pos = generate_portfolio(seed)
    total = sum(p.price * p.total_qty for p in pos)
    W = int(total * random.Random(seed).uniform(0.15, 0.6))
    opt = brute_force(pos, W, SALE, P0, rules)
    plans = {"pro_rata": pro_rata(pos, W), "largest": largest_first(pos, W),
             "greedy": greedy_tax_aware(pos, W, SALE, P0, rules)}
    # the optimum's reported tax must match an independent end-to-end evaluation
    assert evaluate_plan(pos, opt.quantities, SALE, P0, rules).tax == opt.tax
    for name, x in plans.items():
        ev = evaluate_plan(pos, x, SALE, P0, rules)
        assert ev.proceeds >= W, name
        assert ev.tax >= opt.tax, name


def test_oversized_withdrawal_rejected(rules):
    pos = hand_case()
    with pytest.raises(ValueError):
        pro_rata(pos, 10**12)
    with pytest.raises(ValueError):
        brute_force(pos, 10**12, SALE, P0, rules)
