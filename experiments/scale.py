"""Solver vs greedy vs pro-rata at larger sizes, with solve time. Synthetic, seeded.
Run: python experiments/scale.py"""
import random, sys, time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from engine.baselines import greedy_tax_aware, pro_rata
from engine.instances import generate_portfolio
from engine.plan import evaluate_plan
from engine.rules import load_rules
from engine.solver import solve
from engine.tax import TaxProfile

rules = load_rules(ROOT / "rules" / "fy2026_27.json")
SALE, P0, N = date(2026, 11, 5), TaxProfile(), 5
print(f"{N} seeds per size; lots = positions x 4; W = 20-50% of value; time limit 20s per stage")
print(f"{'positions':>9}{'lots':>6}{'solver s (mean/max)':>22}{'optimal':>9}{'solver tax':>12}{'greedy tax':>12}{'pro-rata tax':>14}{'greedy worse':>14}")
for n in (10, 25):
    ts, opt, tx, gx, px, worse = [], 0, 0, 0, 0, 0
    for seed in range(N):
        pos = generate_portfolio(seed, n_positions=n, lots_per_position=4,
                                 price_range=(100, 6000), qty_range=(10, 400))
        total = sum(p.price * p.total_qty for p in pos)
        W = int(total * random.Random(seed).uniform(0.2, 0.5))
        t0 = time.time(); r = solve(pos, W, SALE, P0, rules, time_limit=20); ts.append(time.time() - t0)
        opt += r.status == "OPTIMAL"; tx += r.tax
        g = evaluate_plan(pos, greedy_tax_aware(pos, W, SALE, P0, rules), SALE, P0, rules).tax
        gx += g; worse += g > r.tax
        px += evaluate_plan(pos, pro_rata(pos, W), SALE, P0, rules).tax
    print(f"{n:9}{4*n:6}{sum(ts)/N:12.2f}/{max(ts):<8.2f}{opt:>7}/{N}{tx/N/100:12,.0f}{gx/N/100:12,.0f}{px/N/100:14,.0f}{worse:>11}/{N}")
