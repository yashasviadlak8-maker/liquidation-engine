"""HTTP API. Run: uvicorn api.main:app --reload"""
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from ai.explain import explain
from ai.intent import parse_request
from ai.llm import get_client
from api.sample import sample_positions
from engine.baselines import greedy_tax_aware, largest_first, pro_rata
from engine.models import Lot, Position
from engine.plan import evaluate_plan
from engine.rules import load_rules
from engine.solver import solve
from engine.tax import TaxProfile, compute_tax
from ingest.tradebook import build_positions, parse_tradebook, to_paise

ROOT = Path(__file__).resolve().parent.parent
RULES = load_rules(ROOT / "rules" / "fy2026_27.json")
app = FastAPI(title="Withdrawal planner")


def paise(x) -> int:
    return int((Decimal(str(x)) * 100).to_integral_value(ROUND_HALF_UP))


class LotIn(BaseModel):
    buy_date: date
    qty: int = Field(gt=0)
    unit_cost: float = Field(ge=0)


class PositionIn(BaseModel):
    account: str = "A"
    symbol: str
    price: float = Field(gt=0)
    lots: list[LotIn] = Field(min_length=1)


class ProfileIn(BaseModel):
    ytd_st: float = 0
    ytd_lt: float = 0
    bf_st_loss: float = Field(default=0, ge=0)
    bf_lt_loss: float = Field(default=0, ge=0)


class PlanRequest(BaseModel):
    positions: list[PositionIn]
    amount: float = Field(gt=0)
    sale_date: date = date(2026, 11, 5)
    profile: ProfileIn = ProfileIn()
    exclude: list[str] = []
    max_positions: Optional[int] = Field(default=None, ge=1)


class IngestRequest(BaseModel):
    csv_text: str
    prices: dict[str, float] = {}


class ParseRequestIn(BaseModel):
    text: str
    symbols: list[str]


def to_positions(ps):
    return [Position(p.account, p.symbol, paise(p.price),
                     tuple(Lot(l.buy_date, l.qty, paise(l.unit_cost)) for l in p.lots)) for p in ps]


def rup(x):
    return round(x / 100, 2)


@app.get("/api/health")
def health():
    return {"ok": True, "fy": RULES.fy, "llm": get_client() is not None}


@app.get("/api/sample")
def sample():
    return {"positions": sample_positions(),
            "note": "Buy dates are assumed (your screenshot has none). Edit them before trusting the plan."}


@app.post("/api/ingest")
def ingest(req: IngestRequest):
    try:
        lots, last, issues = parse_tradebook(req.csv_text)
    except (ValueError, KeyError) as e:
        raise HTTPException(422, str(e))
    positions, more = build_positions(lots, last, {k.upper(): paise(v) for k, v in req.prices.items()})
    return {"positions": [{"account": p.account, "symbol": p.symbol, "price": rup(p.price),
                           "lots": [{"buy_date": l.buy_date.isoformat(), "qty": l.qty, "unit_cost": rup(l.unit_cost)}
                                    for l in p.lots]} for p in positions],
            "issues": issues + more}


@app.post("/api/parse-request")
def parse_req(req: ParseRequestIn):
    return parse_request(req.text, req.symbols, get_client()).model_dump()


@app.post("/api/plan")
def plan(req: PlanRequest):
    positions = to_positions(req.positions)
    keys = {p.key for p in positions}
    excl = frozenset(k for k in keys if k[1] in {e.upper() for e in req.exclude} or k[1] in req.exclude)
    prof = TaxProfile(paise(req.profile.ytd_st), paise(req.profile.ytd_lt),
                      paise(req.profile.bf_st_loss), paise(req.profile.bf_lt_loss))
    W = paise(req.amount)
    avail = [p for p in positions if p.key not in excl]
    if W > sum(p.price * p.total_qty for p in avail):
        raise HTTPException(422, "Amount exceeds the value of the holdings you allowed to be sold.")
    try:
        r = solve(positions, W, req.sale_date, prof, RULES, time_limit=20, excluded=excl, max_positions=req.max_positions)
    except RuntimeError:
        raise HTTPException(422, "No feasible plan under these constraints (try allowing more positions or a smaller amount).")
    ev = evaluate_plan(positions, r.quantities, req.sale_date, prof, RULES)
    after = compute_tax(prof.ytd_st + ev.st_gain, prof.ytd_lt + ev.lt_gain, RULES, prof.bf_st_loss, prof.bf_lt_loss)

    base = {"pro_rata": pro_rata(avail, W), "largest_first": largest_first(avail, W)}
    if sum(len(p.lots) for p in avail) <= 60:
        base["greedy"] = greedy_tax_aware(avail, W, req.sale_date, prof, RULES, chunk_value=max(500_000, W // 50))
    baselines = {}
    for name, x in base.items():
        b = evaluate_plan(avail, x, req.sale_date, prof, RULES)
        baselines[name] = {"tax": rup(b.tax), "proceeds": rup(b.proceeds)}

    sells = []
    for p in positions:
        cs = ev.consumptions.get(p.key)
        if not cs:
            continue
        sells.append({"account": p.account, "symbol": p.symbol, "qty": r.quantities[p.key],
                      "proceeds": rup(r.quantities[p.key] * p.price),
                      "lots": [{"buy_date": p.lots[c.lot_index].buy_date.isoformat(), "qty": c.qty, "gain": rup(c.gain),
                                "term": "long" if c.long_term else "short"} for c in cs]})
    out = {"status": r.status, "tax_optimal": r.tax_optimal, "solve_seconds": round(r.solve_seconds, 2),
           "proceeds": rup(ev.proceeds), "tax": rup(ev.tax), "st_gain": rup(ev.st_gain), "lt_gain": rup(ev.lt_gain),
           "exemption_used": rup(after.exemption_used), "sells": sells, "baselines": baselines,
           "savings_vs_pro_rata": rup(baselines["pro_rata"]["tax"] * 100 - ev.tax)}
    out["explanation"], out["explanation_source"] = explain(out, get_client())
    out["disclaimer"] = ("Planning aid showing the tax effect of choices under the modelled rules (listed equity, one FY, "
                         "no surcharge or charges). Not tax or investment advice.")
    return out


@app.get("/")
def index():
    return FileResponse(ROOT / "web" / "index.html")
