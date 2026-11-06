"""Evaluate a candidate plan (shares sold per position) end to end."""
from dataclasses import dataclass
from datetime import date

from .fifo import consume
from .rules import Rules
from .tax import TaxProfile, incremental_tax


@dataclass(frozen=True)
class PlanEval:
    proceeds: int
    st_gain: int
    lt_gain: int
    tax: int            # incremental tax caused by this plan
    consumptions: dict  # position key -> list[Consumption]


def evaluate_plan(positions, quantities: dict, sale_date: date, profile: TaxProfile, rules: Rules) -> PlanEval:
    proceeds = st = lt = 0
    cons = {}
    for p in positions:
        q = quantities.get(p.key, 0)
        if q == 0:
            continue
        cs = consume(p, q, sale_date, rules.lt_holding_months)
        cons[p.key] = cs
        proceeds += q * p.price
        for c in cs:
            if c.long_term:
                lt += c.gain
            else:
                st += c.gain
    tax, _ = incremental_tax(st, lt, profile, rules)
    return PlanEval(proceeds, st, lt, tax, cons)
