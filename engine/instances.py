"""Seeded synthetic portfolios for tests and experiments."""
import random
from datetime import date, timedelta

from .models import Lot, Position


def generate_portfolio(seed, n_positions=3, lots_per_position=2, sale_date=date(2026, 11, 5),
                       price_range=(5000, 60000), qty_range=(3, 9)):
    rng = random.Random(seed)
    positions = []
    for i in range(n_positions):
        price = rng.randint(*price_range) * 100
        lots = []
        for _ in range(lots_per_position):
            months = rng.randint(1, 48)
            buy = sale_date - timedelta(days=int(months * 30.4))
            lots.append(Lot(buy, rng.randint(*qty_range), int(price * rng.uniform(0.6, 1.4))))
        positions.append(Position("A", f"S{i}", price, tuple(lots)))
    return positions


def generate_hard_portfolio(seed, n_positions=10, lots_per_position=4, sale_date=date(2026, 11, 5),
                            price_range=(100, 6000), qty_range=(10, 400)):
    """Gains-heavy portfolio with many lots near the 12-month boundary, so tax cannot simply be offset."""
    rng = random.Random(seed)
    positions = []
    for i in range(n_positions):
        price = rng.randint(*price_range) * 100
        lots = []
        for _ in range(lots_per_position):
            months = rng.randint(10, 14) if rng.random() < 0.4 else rng.randint(1, 48)
            buy = sale_date - timedelta(days=int(months * 30.4) + rng.randint(-10, 10))
            lots.append(Lot(buy, rng.randint(*qty_range), int(price * rng.uniform(0.3, 1.15))))
        positions.append(Position("A", f"S{i}", price, tuple(lots)))
    return positions


def generate_profile(seed):
    """Year-to-date gains and brought-forward losses (paise) that interact with the exemption."""
    from .tax import TaxProfile
    rng = random.Random(seed * 31 + 5)
    r = lambda lo, hi: rng.randint(lo, hi) * 100
    return TaxProfile(
        ytd_lt=rng.choice([0, r(60000, 150000)]),
        ytd_st=rng.choice([0, r(10000, 60000), -r(10000, 60000)]),
        bf_st_loss=rng.choice([0, 0, r(10000, 50000)]),
        bf_lt_loss=rng.choice([0, 0, r(20000, 100000)]))
