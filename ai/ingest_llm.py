"""Fallback ingestion for PDFs/screenshots/odd formats (text already extracted/OCR'd).
Every field the model returns must be grounded in the source text; missing buy dates are flagged, never guessed."""
import re
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field

from .llm import MODELS, extract_json

SYSTEM = ('Extract share lots from the statement as JSON only: {"lots": [{"symbol": str, "buy_date": "YYYY-MM-DD" or null, '
          '"qty": int, "unit_cost_rupees": number}]}. Use null for a missing buy date. Never guess values not in the text.')


class LotDraft(BaseModel):
    symbol: str
    buy_date: Optional[date] = None
    qty: int = Field(gt=0)
    unit_cost_rupees: float = Field(gt=0)


def _date_forms(d: date):
    return {d.isoformat(), d.strftime("%d-%m-%Y"), d.strftime("%d/%m/%Y"), d.strftime("%d-%b-%Y"), d.strftime("%d %b %Y")}


def _num_in(text: str, x: float) -> bool:
    forms = {f"{x:g}", f"{x:.2f}", f"{x:,.2f}", f"{x:,.0f}", str(int(x)) if float(x).is_integer() else ""}
    return any(f and re.search(rf"(?<![\d.]){re.escape(f)}(?![\d])", text) for f in forms)


def parse_statement_text(text: str, client):
    raw = extract_json(client.complete(SYSTEM, text, MODELS["parse"]))
    lots, issues = [], []
    for item in raw.get("lots", []):
        try:
            lot = LotDraft.model_validate(item)
        except Exception:
            issues.append(f"Rejected malformed row: {item}")
            continue
        sym = lot.symbol.strip().upper()
        if sym.lower() not in text.lower():
            issues.append(f"Rejected {sym}: symbol not found in the statement text")
            continue
        if not (_num_in(text, lot.qty) and _num_in(text, lot.unit_cost_rupees)):
            issues.append(f"Rejected {sym}: quantity or cost not found in the statement text")
            continue
        d = lot.buy_date
        if d is not None and not any(f in text for f in _date_forms(d)):
            issues.append(f"{sym}: buy date {d} is not in the statement; ignored")
            d = None
        if d is None:
            issues.append(f"{sym}: buy date missing. Needed for short/long-term split; enter it manually.")
        lots.append({"symbol": sym, "buy_date": d, "qty": lot.qty, "unit_cost_rupees": lot.unit_cost_rupees})
    return lots, issues
