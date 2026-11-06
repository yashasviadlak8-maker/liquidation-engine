"""Solver-only timing on 200-lot synthetic portfolios. Run: python experiments/solver_time.py"""
import random, sys, time
from datetime import date
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from engine.instances import generate_portfolio
from engine.rules import load_rules
from engine.solver import solve
from engine.tax import TaxProfile

rules = load_rules(ROOT / "rules" / "fy2026_27.json")
SALE, ts = date(2026, 11, 5), []
for seed in range(10):
    pos = generate_portfolio(seed, n_positions=50, lots_per_position=4, price_range=(100, 6000), qty_range=(10, 400))
    total = sum(p.price * p.total_qty for p in pos)
    W = int(total * random.Random(seed).uniform(0.2, 0.5))
    t = time.time(); r = solve(pos, W, SALE, TaxProfile(), rules, time_limit=20); ts.append(time.time() - t)
    print(f"seed {seed}: {r.status}, tax Rs {r.tax/100:,.0f}, {ts[-1]:.2f}s", flush=True)
print(f"200 lots: mean {sum(ts)/len(ts):.2f}s, max {max(ts):.2f}s")
