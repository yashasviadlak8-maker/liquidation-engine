"""Exhaustive optimum for small instances. Ground truth for the exact solver.
Objective is lexicographic: minimise tax, then minimise proceeds (sell as little as possible)."""
from dataclasses import dataclass
from itertools import product
from math import prod

from .fifo import consume
from .tax import incremental_tax


@dataclass(frozen=True)
class Solution:
    quantities: dict
    tax: int
    proceeds: int


def brute_force(positions, W, sale_date, profile, rules, max_states=2_000_000,
                excluded=frozenset(), max_positions=None):
    top = lambda p: 0 if p.key in excluded else p.total_qty
    states = prod(top(p) + 1 for p in positions)
    if states > max_states:
        raise ValueError(f"{states} states exceeds max_states={max_states}")
    tables = []
    for p in positions:
        row = []
        for x in range(top(p) + 1):
            st = lt = 0
            for c in consume(p, x, sale_date, rules.lt_holding_months):
                if c.long_term:
                    lt += c.gain
                else:
                    st += c.gain
            row.append((x * p.price, st, lt))
        tables.append(row)
    best = None
    for combo in product(*[range(len(t)) for t in tables]):
        proceeds = st = lt = 0
        for t, i in zip(tables, combo):
            a, b, c = t[i]
            proceeds += a; st += b; lt += c
        if proceeds < W:
            continue
        if max_positions is not None and sum(1 for i in combo if i > 0) > max_positions:
            continue
        tax, _ = incremental_tax(st, lt, profile, rules)
        key = (tax, proceeds)
        if best is None or key < best[0]:
            best = (key, combo)
    if best is None:
        raise ValueError("infeasible: withdrawal exceeds portfolio value")
    (tax, proceeds), combo = best
    return Solution({p.key: x for p, x in zip(positions, combo)}, tax, proceeds)
