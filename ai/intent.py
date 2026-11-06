"""Free text -> structured constraints. The LLM translates; the solver decides.
The caller must show `confirm` to the user and get a yes before solving."""
import re
from typing import Optional

from pydantic import BaseModel, Field, ValidationError

from .llm import MODELS, extract_json

SYSTEM = ("Convert the user's withdrawal request into JSON only, no prose: "
          '{"amount_rupees": number or null, "exclude": [symbols from the allowed list], '
          '"max_positions": integer or null, "deadline_note": string or null}. '
          "Use only the allowed symbols. Never invent values the user did not state.")


class Constraints(BaseModel):
    amount_rupees: Optional[float] = Field(default=None, gt=0)
    exclude: list[str] = []
    max_positions: Optional[int] = Field(default=None, ge=1)
    deadline_note: Optional[str] = None


class ParsedRequest(BaseModel):
    constraints: Constraints
    confirm: str
    source: str            # "llm" or "rules"
    warnings: list[str] = []


UNITS = {"crore": 10**7, "cr": 10**7, "lakh": 10**5, "lakhs": 10**5, "lac": 10**5, "l": 10**5,
         "k": 1000, "thousand": 1000}
NEG = re.compile(r"don'?t touch|do not touch|exclude|except|not sell|don'?t sell|without|avoid|keep|leave", re.I)


def regex_parse(text: str, symbols: list[str]) -> Constraints:
    amount = None
    m = re.search(r"(?:₹|rs\.?\s*)?\s*(\d[\d,]*(?:\.\d+)?)\s*(crore|cr|lakhs?|lac|l|k|thousand)?\b", text, re.I)
    for m in re.finditer(r"(?:₹|rs\.?\s*)?\s*(\d[\d,]*(?:\.\d+)?)\s*(crore|cr|lakhs?|lac|l|k|thousand)?\b", text, re.I):
        val, unit = float(m.group(1).replace(",", "")), (m.group(2) or "").lower()
        if unit or val >= 1000:
            amount = val * UNITS.get(unit, 1)
            break
    exclude = []
    for clause in re.split(r"[,;.]| and ", text):
        if NEG.search(clause):
            for s in symbols:
                if s.lower() in clause.lower() or s.split()[0].lower() in clause.lower().split():
                    if s not in exclude:
                        exclude.append(s)
    mp = re.search(r"(?:max(?:imum)?|at most|only|up to)\s+(\d+)\s*(?:trades|stocks|scrips|positions|sells)", text, re.I)
    return Constraints(amount_rupees=amount, exclude=exclude, max_positions=int(mp.group(1)) if mp else None)


def _confirm(c: Constraints) -> str:
    parts = [f"raise ₹{c.amount_rupees:,.0f}" if c.amount_rupees else "amount not found"]
    if c.exclude:
        parts.append("do not sell " + ", ".join(c.exclude))
    if c.max_positions:
        parts.append(f"sell at most {c.max_positions} positions")
    if c.deadline_note:
        parts.append(f"timing note: {c.deadline_note} (v1 plans for one financial year; the sale date is set separately)")
    return "I understood: " + "; ".join(parts) + "."


def parse_request(text: str, symbols: list[str], client=None) -> ParsedRequest:
    warnings = []
    if client is not None:
        try:
            raw = client.complete(SYSTEM, f"Allowed symbols: {symbols}\nRequest: {text}", MODELS["intent"])
            c = Constraints.model_validate(extract_json(raw))
            known = {s.lower(): s for s in symbols}
            kept = [known[e.lower()] for e in c.exclude if e.lower() in known]
            if len(kept) != len(c.exclude):
                warnings.append("Some excluded names were not in your portfolio and were dropped.")
            c = c.model_copy(update={"exclude": kept})
            return ParsedRequest(constraints=c, confirm=_confirm(c), source="llm", warnings=warnings)
        except (ValueError, ValidationError, Exception) as e:   # any failure falls back to rules
            warnings.append(f"LLM parsing failed ({type(e).__name__}); used rule-based parsing.")
    c = regex_parse(text, symbols)
    return ParsedRequest(constraints=c, confirm=_confirm(c), source="rules", warnings=warnings)
