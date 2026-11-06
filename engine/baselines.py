"""Baseline sell plans. Each returns {position key: shares sold} with proceeds >= W."""
from fractions import Fraction
from math import ceil

from .plan import evaluate_plan


def _check(positions, W):
    if W > sum(p.price * p.total_qty for p in positions):
        raise ValueError("withdrawal exceeds portfolio value")


def pro_rata(positions, W):
    """Sell the same fraction of every position (floor, then top up the largest deficits)."""
    _check(positions, W)
    total = sum(p.price * p.total_qty for p in positions)
    target = {p.key: Fraction(W * p.price * p.total_qty, total) for p in positions}
    x = {p.key: int(target[p.key] // p.price) for p in positions}
    proceeds = sum(x[p.key] * p.price for p in positions)
    while proceeds < W:
        cand = [p for p in positions if x[p.key] < p.total_qty]
        p = max(cand, key=lambda q: (target[q.key] - x[q.key] * q.price, q.key))
        x[p.key] += 1
        proceeds += p.price
    return x


def largest_first(positions, W):
    """Naive: empty the biggest positions first until the target is met."""
    _check(positions, W)
    x = {p.key: 0 for p in positions}
    proceeds = 0
    for p in sorted(positions, key=lambda q: -q.price * q.total_qty):
        if proceeds >= W:
            break
        take = min(p.total_qty, ceil((W - proceeds) / p.price))
        x[p.key] = take
        proceeds += take * p.price
    return x


def greedy_tax_aware(positions, W, sale_date, profile, rules, chunk_value=500_000):
    """Strong heuristic: repeatedly sell the chunk with the lowest marginal tax per rupee.
    FIFO-correct (every candidate is evaluated through evaluate_plan). Not guaranteed optimal."""
    _check(positions, W)
    x = {p.key: 0 for p in positions}
    proceeds = 0
    while proceeds < W:
        base = evaluate_plan(positions, x, sale_date, profile, rules).tax
        best = None
        for p in positions:
            room = p.total_qty - x[p.key]
            if room == 0:
                continue
            u = min(room, max(1, chunk_value // p.price), ceil((W - proceeds) / p.price))
            x[p.key] += u
            t = evaluate_plan(positions, x, sale_date, profile, rules).tax
            x[p.key] -= u
            key = (Fraction(t - base, u * p.price), p.key)
            if best is None or key < best[0]:
                best = (key, p, u)
        _, p, u = best
        x[p.key] += u
        proceeds += u * p.price
    return x
