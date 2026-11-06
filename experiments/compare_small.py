"""Small-instance comparison: baselines vs exhaustive optimum (synthetic, seeded).
Run: python experiments/compare_small.py"""
import random
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from engine.baselines import pro_rata, largest_first, greedy_tax_aware
from engine.bruteforce import brute_force
from engine.instances import generate_portfolio
from engine.plan import evaluate_plan
from engine.rules import load_rules
from engine.tax import TaxProfile

rules = load_rules(ROOT / "rules" / "fy2026_27.json")
SALE, P0, N = date(2026, 11, 5), TaxProfile(), 200
names = ["optimum", "pro_rata", "largest_first", "greedy"]
tax = {n: [] for n in names}
for seed in range(N):
    pos = generate_portfolio(seed)
    total = sum(p.price * p.total_qty for p in pos)
    W = int(total * random.Random(seed).uniform(0.15, 0.6))
    tax["optimum"].append(brute_force(pos, W, SALE, P0, rules).tax)
    for n, x in (("pro_rata", pro_rata(pos, W)), ("largest_first", largest_first(pos, W)),
                 ("greedy", greedy_tax_aware(pos, W, SALE, P0, rules))):
        tax[n].append(evaluate_plan(pos, x, SALE, P0, rules).tax)
print(f"{N} synthetic instances (3 positions x 2 lots), seeds 0..{N-1}")
print(f"{'method':14}{'mean tax (Rs)':>15}{'suboptimal %':>15}{'mean excess (Rs)':>18}")
for n in names:
    ex = [t - o for t, o in zip(tax[n], tax["optimum"])]
    print(f"{n:14}{sum(tax[n])/N/100:15,.0f}{100*sum(e>0 for e in ex)/N:15.1f}{sum(ex)/N/100:18,.0f}")
