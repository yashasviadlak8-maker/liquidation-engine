"""Plan explanations. Numbers come only from the solver's output; the LLM may only narrate them."""
import json
import re

from .llm import MODELS

SYSTEM = ("Explain this tax-minimising sell plan to an investor in 3-4 plain sentences. "
          "Use ONLY the numbers in the JSON facts, written exactly as given. Do not compute anything new. "
          "Do not give investment advice.")
CONSTANTS = {12, 20, 125000, 4}   # rule parameters that may appear (holding months, STCG %, exemption, cess %)
CONSTANT_FLOATS = {12.5}


def inr(x) -> str:
    return "₹" + f"{round(x):,}"


def facts_from_plan(plan: dict) -> dict:
    keys = ["proceeds", "tax", "st_gain", "lt_gain", "exemption_used"]
    f = {k: round(plan[k]) for k in keys if k in plan}
    for name, b in plan.get("baselines", {}).items():
        f[f"{name}_tax"] = round(b["tax"])
    if "savings_vs_pro_rata" in plan:
        f["savings_vs_pro_rata"] = round(plan["savings_vs_pro_rata"])
    f["positions_sold"] = len(plan.get("sells", []))
    return f


def template_explanation(plan: dict) -> str:
    f = facts_from_plan(plan)
    s = [f"This plan raises {inr(f['proceeds'])} and the extra tax is {inr(f['tax'])}."]
    if "pro_rata_tax" in f:
        s.append(f"Selling the same fraction of every holding would cost {inr(f['pro_rata_tax'])}, "
                 f"so this plan saves {inr(f['savings_vs_pro_rata'])}.")
    s.append(f"Realised gains: short-term {inr(f['st_gain'])}, long-term {inr(f['lt_gain'])}; "
             f"{inr(f['exemption_used'])} of the ₹125,000 long-term exemption is used.")
    s.append(f"It sells from {f['positions_sold']} position(s), always taking the oldest lots first as the law requires.")
    return " ".join(s)


def numbers_faithful(text: str, facts: dict) -> bool:
    allowed = {round(v) for v in facts.values()} | CONSTANTS
    for tok in re.findall(r"\d[\d,]*\.?\d*", text):
        v = float(tok.replace(",", "").rstrip("."))
        if v in CONSTANT_FLOATS:
            continue
        if round(v) not in allowed:
            return False
    return True


def explain(plan: dict, client=None):
    """Returns (text, source). Falls back to the template if the LLM output uses any unlisted number."""
    base = template_explanation(plan)
    if client is None:
        return base, "template"
    facts = facts_from_plan(plan)
    try:
        text = client.complete(SYSTEM, json.dumps(facts), MODELS["explain"]).strip()
        if text and numbers_faithful(text, facts):
            return text, "llm"
    except Exception:
        pass
    return base, "template"
