"""Tax parameters live in versioned JSON, never hardcoded in logic."""
import json
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path


@dataclass(frozen=True)
class Rules:
    fy: str
    lt_holding_months: int      # long-term if held MORE than this many months
    stcg_rate: Fraction         # s.111A
    ltcg_rate: Fraction
    ltcg_exemption: int         # paise, per FY
    cess_rate: Fraction


def load_rules(path) -> Rules:
    d = json.loads(Path(path).read_text())
    return Rules(
        fy=d["fy"],
        lt_holding_months=int(d["lt_holding_months"]),
        stcg_rate=Fraction(d["stcg_rate"]),
        ltcg_rate=Fraction(d["ltcg_rate"]),
        ltcg_exemption=int(d["ltcg_exemption_paise"]),
        cess_rate=Fraction(d["cess_rate"]),
    )
