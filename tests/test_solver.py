import random
from datetime import date
import pytest
from engine.baselines import greedy_tax_aware, pro_rata
from engine.bruteforce import brute_force
from engine.instances import generate_portfolio
from engine.plan import evaluate_plan
from engine.solver import solve
from engine.tax import TaxProfile
from tests.test_baselines_bruteforce import hand_case

R = 100
SALE = date(2026, 11, 5)


def test_hand_case(rules):
    r = solve(hand_case(), 200000 * R, SALE, TaxProfile(), rules)
    assert r.status == "OPTIMAL" and r.tax == 0 and r.proceeds == 200000 * R


def profile_for(seed):
    rng = random.Random(seed * 7 + 1)
    pick = lambda: rng.choice([0, 0, rng.randint(1, 3) * 50000 * R])
    sign = lambda: rng.choice([-1, 1])
    return TaxProfile(ytd_st=sign() * pick(), ytd_lt=sign() * pick(),
                      bf_st_loss=pick(), bf_lt_loss=pick())


@pytest.mark.parametrize("seed", range(80))
def test_matches_brute_force(rules, seed):
    pos = generate_portfolio(seed)
    prof = profile_for(seed)
    total = sum(p.price * p.total_qty for p in pos)
    W = int(total * random.Random(seed).uniform(0.15, 0.6))
    bf = brute_force(pos, W, SALE, prof, rules)
    r = solve(pos, W, SALE, prof, rules)
    assert r.status == "OPTIMAL"
    assert (r.tax, r.proceeds) == (bf.tax, bf.proceeds)
    assert evaluate_plan(pos, r.quantities, SALE, prof, rules).tax == r.tax


def test_screenshot_scale_portfolio(rules):
    pos = generate_portfolio(1, n_positions=12, lots_per_position=2,
                             price_range=(90, 6500), qty_range=(10, 600))
    total = sum(p.price * p.total_qty for p in pos)
    W = total // 4
    r = solve(pos, W, SALE, TaxProfile(), rules)
    assert r.status == "OPTIMAL" and r.proceeds >= W
    assert r.tax <= evaluate_plan(pos, pro_rata(pos, W), SALE, TaxProfile(), rules).tax
    assert r.tax <= evaluate_plan(pos, greedy_tax_aware(pos, W, SALE, TaxProfile(), rules), SALE, TaxProfile(), rules).tax


def test_oversized_rejected(rules):
    with pytest.raises(ValueError):
        solve(hand_case(), 10**12, SALE, TaxProfile(), rules)


@pytest.mark.parametrize("seed", range(40))
def test_constraints_match_brute_force(rules, seed):
    pos = generate_portfolio(seed)
    rng = random.Random(seed)
    excluded = frozenset([pos[0].key]) if seed % 2 == 0 else frozenset()
    k = rng.choice([None, 1, 2])
    prof = profile_for(seed)
    avail = sum(p.price * p.total_qty for p in pos if p.key not in excluded)
    W = int(avail * rng.uniform(0.1, 0.4))
    try:
        bf = brute_force(pos, W, SALE, prof, rules, excluded=excluded, max_positions=k)
    except ValueError:
        with pytest.raises(RuntimeError):
            solve(pos, W, SALE, prof, rules, excluded=excluded, max_positions=k)
        return
    r = solve(pos, W, SALE, prof, rules, excluded=excluded, max_positions=k)
    assert (r.tax, r.proceeds) == (bf.tax, bf.proceeds)
    assert all(r.quantities[e] == 0 for e in excluded)
    assert k is None or sum(1 for v in r.quantities.values() if v > 0) <= k
