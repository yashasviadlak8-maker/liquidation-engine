"""Exact minimum-tax withdrawal via CP-SAT (integer paise throughout).

Decision: y[p,j], shares sold from lot j of position p, constrained to FIFO order
(lot j+1 can only be used if lot j is fully consumed). Gains are linear in y.
The tax function (set-off, brought-forward losses, exemption, rounding) is encoded
with min/max equalities so it matches engine.tax.compute_tax exactly.
Objective is lexicographic like brute force: minimise tax, then proceeds.
"""
from dataclasses import dataclass
from fractions import Fraction
from math import lcm

from ortools.sat.python import cp_model

from .fifo import is_long_term
from .plan import evaluate_plan


@dataclass(frozen=True)
class SolverResult:
    quantities: dict
    tax: int            # recomputed independently via evaluate_plan
    proceeds: int
    status: str         # OPTIMAL / FEASIBLE (FEASIBLE: tax optimal but proceeds tie-break not proven)
    solve_seconds: float
    tax_optimal: bool = True    # stage 1 proved the minimum tax
    tax_seconds: float = 0.0    # stage 1 wall time


def solve(positions, W, sale_date, profile, rules, time_limit=30.0, workers=8,
          excluded=frozenset(), max_positions=None) -> SolverResult:
    total = sum(p.price * p.total_qty for p in positions if p.key not in excluded)
    if W > total:
        raise ValueError("withdrawal exceeds portfolio value")

    m = cp_model.CpModel()
    pos_y = {p.key: [] for p in positions}
    ys = {}                       # (position key, lot position in FIFO order) -> var
    st_terms, lt_terms, proc_terms = [], [], []
    bound = 0
    for p in positions:
        order = sorted(range(len(p.lots)), key=lambda i: (p.lots[i].buy_date, i))
        prev_z = None
        for k, i in enumerate(order):
            lot = p.lots[i]
            if lot.qty == 0:
                continue
            y = m.NewIntVar(0, 0 if p.key in excluded else lot.qty, f"y_{p.account}_{p.symbol}_{k}")
            pos_y[p.key].append(y)
            if prev_z is not None:
                m.Add(y <= lot.qty * prev_z)           # FIFO: previous lot must be fully used
            z = m.NewBoolVar(f"z_{p.account}_{p.symbol}_{k}")
            m.Add(y >= lot.qty * z)                    # z=1 -> lot fully consumed
            prev_z = z
            ys[(p.key, i)] = y
            g = p.price - lot.unit_cost
            (lt_terms if is_long_term(lot.buy_date, sale_date, rules.lt_holding_months) else st_terms).append(g * y)
            proc_terms.append(p.price * y)
            bound += abs(g) * lot.qty
    if max_positions is not None:
        flags = []
        for p in positions:
            f = m.NewBoolVar(f"sold_{p.account}_{p.symbol}")
            m.Add(sum(pos_y[p.key]) <= p.total_qty * f)
            flags.append(f)
        m.Add(sum(flags) <= max_positions)
    B = (bound + abs(profile.ytd_st) + abs(profile.ytd_lt) + profile.bf_st_loss
         + profile.bf_lt_loss + rules.ltcg_exemption) * 2 + 1

    def var(lo, hi, name):
        return m.NewIntVar(lo, hi, name)

    def pos_part(expr, name):
        v = var(0, B, name)
        m.AddMaxEquality(v, [expr, 0])
        return v

    def minimum(a, b, name):
        v = var(0, B, name)
        m.AddMinEquality(v, [a, b])
        return v

    st = var(-B, B, "st"); m.Add(st == sum(st_terms) + profile.ytd_st)
    lt = var(-B, B, "lt"); m.Add(lt == sum(lt_terms) + profile.ytd_lt)

    # current-year set-off: ST loss may offset LT gain (never the reverse)
    used = minimum(pos_part(-st, "neg_st"), pos_part(lt, "pos_lt"), "used")
    st1 = var(-B, B, "st1"); m.Add(st1 == st + used)
    lt1 = var(-B, B, "lt1"); m.Add(lt1 == lt - used)
    # brought-forward ST loss: against ST gain, then LT gain
    u1 = minimum(profile.bf_st_loss, pos_part(st1, "pos_st1"), "u1")
    st2 = var(-B, B, "st2"); m.Add(st2 == st1 - u1)
    u2 = minimum(profile.bf_st_loss - u1, pos_part(lt1, "pos_lt1"), "u2")
    lt2 = var(-B, B, "lt2"); m.Add(lt2 == lt1 - u2)
    # brought-forward LT loss: against LT gain only
    u3 = minimum(profile.bf_lt_loss, pos_part(lt2, "pos_lt2"), "u3")
    lt3 = var(-B, B, "lt3"); m.Add(lt3 == lt2 - u3)

    taxable_st = pos_part(st2, "taxable_st")
    lt_pos = pos_part(lt3, "lt_pos")
    ex = minimum(lt_pos, rules.ltcg_exemption, "ex")
    taxable_lt = var(0, B, "taxable_lt"); m.Add(taxable_lt == lt_pos - ex)

    # tax = round_half_up((s*taxable_st + l*taxable_lt) * (1+cess)), exactly, in integers
    a = rules.stcg_rate * (1 + rules.cess_rate)
    b = rules.ltcg_rate * (1 + rules.cess_rate)
    D = lcm(a.denominator, b.denominator)
    an, bn = int(a * D), int(b * D)
    N = an * taxable_st + bn * taxable_lt
    tax = var(0, B, "tax")
    m.Add(2 * D * tax <= 2 * N + D)
    m.Add(2 * N + D <= 2 * D * tax + 2 * D - 1)

    proceeds = sum(proc_terms)
    m.Add(proceeds >= W)

    # Lexicographic objective in two stages (a single weighted objective overflows int64
    # on large portfolios): 1) minimise tax, 2) with tax fixed, minimise proceeds.
    s = cp_model.CpSolver()
    s.parameters.num_workers = workers
    s.parameters.max_time_in_seconds = time_limit
    m.Minimize(tax)
    status = s.Solve(m)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise RuntimeError(f"solver status {s.StatusName(status)}")
    wall = s.WallTime()
    tax_seconds, tax_optimal = wall, status == cp_model.OPTIMAL
    final_status = s.StatusName(status)
    vals = {k: s.Value(y) for k, y in ys.items()}
    for k, y in ys.items():
        m.AddHint(y, vals[k])
    m.Add(tax <= s.Value(tax))
    m.Minimize(proceeds)
    s.parameters.max_time_in_seconds = min(time_limit, 3.0)
    status2 = s.Solve(m)
    wall += s.WallTime()
    if status2 == cp_model.OPTIMAL:
        vals = {k: s.Value(y) for k, y in ys.items()}
    elif status2 == cp_model.FEASIBLE:
        vals = {k: s.Value(y) for k, y in ys.items()}
        final_status = "FEASIBLE"
    else:
        final_status = "FEASIBLE"   # tax is optimal; the tie-break on proceeds was not completed

    q = {p.key: 0 for p in positions}
    for (key, _), v in vals.items():
        q[key] += v
    ev = evaluate_plan(positions, q, sale_date, profile, rules)
    return SolverResult(q, ev.tax, ev.proceeds, final_status, wall, tax_optimal, tax_seconds)
