"""Proposes a rules-config update from new law text. Never edits a live rules file: writes
rules/proposed_<fy>.json and returns a diff for a human to review (then tests must pass)."""
import json
from fractions import Fraction
from pathlib import Path

from .llm import MODELS, extract_json

SYSTEM = ('Read the tax-law text and return JSON only with exactly these keys: fy (e.g. "2027-28"), lt_holding_months (int), '
          'stcg_rate and ltcg_rate and cess_rate as fraction strings like "1/5", ltcg_exemption_paise (int). '
          "Copy values from the current config unless the text clearly changes them.")
KEYS = ["fy", "lt_holding_months", "stcg_rate", "ltcg_rate", "ltcg_exemption_paise", "cess_rate"]


def validate_rules(d: dict) -> dict:
    if set(d) != set(KEYS):
        raise ValueError(f"keys must be exactly {KEYS}")
    for k in ("stcg_rate", "ltcg_rate", "cess_rate"):
        if not (0 < Fraction(d[k]) < 1):
            raise ValueError(f"{k} out of range")
    if not (1 <= int(d["lt_holding_months"]) <= 60) or int(d["ltcg_exemption_paise"]) <= 0:
        raise ValueError("holding period or exemption out of range")
    return {k: d[k] for k in KEYS}


def propose_rules_update(current: dict, source_text: str, client, out_dir):
    user = f"Current config: {json.dumps(current)}\n\nLaw text:\n{source_text}"
    proposed = validate_rules(extract_json(client.complete(SYSTEM, user, MODELS["rules"])))
    diff = {k: {"from": current.get(k), "to": proposed[k]} for k in KEYS if current.get(k) != proposed[k]}
    path = None
    if diff:
        path = Path(out_dir) / f"proposed_{proposed['fy']}.json"
        path.write_text(json.dumps(proposed, indent=2))
    return {"diff": diff, "path": str(path) if path else None, "requires_human_review": True}
