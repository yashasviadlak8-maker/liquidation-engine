"""Harness for the LLM-vs-solver experiment: prompt builder and a scorer. No network here."""
import json
from fractions import Fraction

from engine.plan import evaluate_plan
from .llm import extract_json


def fifo_order(p):
    return sorted(range(len(p.lots)), key=lambda i: (p.lots[i].buy_date, i))


def build_prompt(positions, W, sale_date, profile, cot=False) -> str:
    lines = [f"Sale date {sale_date}. Raise at least Rs {W/100:,.2f} from this portfolio with the LEAST capital-gains tax.",
             "Indian listed equity: held more than 12 months = long-term (12.5% above Rs 1,25,000 exemption), else short-term 20%; add 4% cess.",
             "Shares in a demat account are sold FIRST-IN-FIRST-OUT per scrip; you cannot choose lots.",
             f"Gains already realised this year (Rs): short-term {profile.ytd_st/100:,.0f}, long-term {profile.ytd_lt/100:,.0f}. "
             f"Brought-forward losses (Rs): short-term {profile.bf_st_loss/100:,.0f}, long-term {profile.bf_lt_loss/100:,.0f}.", "Holdings:"]
    for p in positions:
        lines.append(f"- {p.symbol}: price Rs {p.price/100:,.2f}")
        for n, i in enumerate(fifo_order(p), 1):
            l = p.lots[i]
            lines.append(f"    lot {n}: bought {l.buy_date}, qty {l.qty}, cost Rs {l.unit_cost/100:,.2f}")
    lines.append('Answer with JSON only: {"sells":[{"symbol":"S0","lot":1,"qty":5}], "claimed_tax_rupees": 0}. '
                 "'lot' is the lot number above.")
    if cot:
        lines.append("Think step by step before the JSON.")
    return "\n".join(lines)


def score(response: str, positions, W, sale_date, profile, rules, optimum_tax: int) -> dict:
    res = dict(valid_json=False, feasible=False, fifo_violation=None, legal_tax=None,
               claimed_tax_error=None, optimality_gap=None)
    try:
        d = extract_json(response)
        sells = d["sells"]
        claimed = float(d.get("claimed_tax_rupees", 0)) * 100
    except Exception:
        return res
    res["valid_json"] = True
    by = {p.symbol: p for p in positions}
    per_lot, totals = {}, {p.key: 0 for p in positions}
    for s in sells:
        p = by.get(s.get("symbol"))
        try:
            n, q = int(s["lot"]), int(s["qty"])
        except Exception:
            return res
        if p is None or not (1 <= n <= len(p.lots)) or q < 0 or q > p.lots[fifo_order(p)[n - 1]].qty:
            return res          # unknown scrip/lot or more shares than the lot holds
        per_lot[(p.symbol, n)] = per_lot.get((p.symbol, n), 0) + q
        totals[p.key] += q
    if any(totals[p.key] > p.total_qty for p in positions):
        return res
    viol = False
    for p in positions:
        qs = [per_lot.get((p.symbol, n), 0) for n in range(1, len(p.lots) + 1)]
        full = [q == p.lots[fifo_order(p)[n]].qty for n, q in enumerate(qs)]
        last = max((n for n, q in enumerate(qs) if q > 0), default=-1)
        viol |= any(not full[n] for n in range(last))      # an earlier lot not fully used
    ev = evaluate_plan(positions, totals, sale_date, profile, rules)   # FIFO applied to their per-scrip totals
    res.update(feasible=ev.proceeds >= W, fifo_violation=viol, legal_tax=ev.tax,
               claimed_tax_error=round(claimed - ev.tax), optimality_gap=ev.tax - optimum_tax)
    return res
