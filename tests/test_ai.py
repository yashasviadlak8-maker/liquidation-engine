import json
from datetime import date
from ai.explain import explain, numbers_faithful, facts_from_plan, template_explanation
from ai.ingest_llm import parse_statement_text
from ai.intent import parse_request, regex_parse
from ai.llm_eval import build_prompt, score
from ai.rules_watch import propose_rules_update
from engine.bruteforce import brute_force
from engine.instances import generate_portfolio
from engine.tax import TaxProfile

SYMS = ["FEDERAL BANK", "KRBL", "NILKAMAL"]


class Fake:
    def __init__(self, reply): self.reply = reply
    def complete(self, system, user, model): return self.reply


class Boom:
    def complete(self, *a): raise RuntimeError("down")


def test_regex_intent():
    c = regex_parse("I need 2.5 lakh, don't touch Federal Bank, max 3 trades", SYMS)
    assert c.amount_rupees == 250000 and c.exclude == ["FEDERAL BANK"] and c.max_positions == 3


def test_llm_intent_validated_and_filtered():
    reply = json.dumps({"amount_rupees": 250000, "exclude": ["federal bank", "TESLA"], "max_positions": None, "deadline_note": "by March"})
    r = parse_request("x", SYMS, Fake(reply))
    assert r.source == "llm" and r.constraints.exclude == ["FEDERAL BANK"] and r.warnings
    assert "₹250,000" in r.confirm


def test_intent_falls_back_when_llm_fails_or_is_garbage():
    for client in (Boom(), Fake("not json")):
        r = parse_request("raise 50k, avoid KRBL", SYMS, client)
        assert r.source == "rules" and r.constraints.amount_rupees == 50000 and r.constraints.exclude == ["KRBL"]


PLAN = {"proceeds": 250000.0, "tax": 1200.0, "st_gain": 5000.0, "lt_gain": 90000.0, "exemption_used": 90000.0,
        "baselines": {"pro_rata": {"tax": 9000.0}}, "savings_vs_pro_rata": 7800.0, "sells": [{}, {}]}


def test_explain_rejects_invented_numbers():
    facts = facts_from_plan(PLAN)
    good = "The plan raises ₹250,000 with ₹1,200 tax, saving ₹7,800 against selling pro-rata."
    bad = "The plan raises ₹250,000 with ₹1,200 tax and saves 31% (₹7,812)."
    assert numbers_faithful(good, facts) and not numbers_faithful(bad, facts)
    assert explain(PLAN, Fake(good)) == (good, "llm")
    assert explain(PLAN, Fake(bad)) == (template_explanation(PLAN), "template")
    assert explain(PLAN, None)[1] == "template"


STATEMENT = "KRBL 150 shares bought 12-03-2025 at 600.00\nFEDERAL BANK 1100 @ 100.00 (date not shown)"


def test_ingest_llm_grounding():
    reply = json.dumps({"lots": [
        {"symbol": "KRBL", "buy_date": "2025-03-12", "qty": 150, "unit_cost_rupees": 600},
        {"symbol": "FEDERAL BANK", "buy_date": "2024-01-01", "qty": 1100, "unit_cost_rupees": 100},   # invented date
        {"symbol": "HDFC", "buy_date": None, "qty": 10, "unit_cost_rupees": 1500},                    # not in text
        {"symbol": "KRBL", "buy_date": None, "qty": 999, "unit_cost_rupees": 600}]})                  # qty not in text
    lots, issues = parse_statement_text(STATEMENT, Fake(reply))
    assert [(l["symbol"], l["buy_date"]) for l in lots] == [("KRBL", date(2025, 3, 12)), ("FEDERAL BANK", None)]
    assert sum("buy date missing" in i for i in issues) == 1 and any("HDFC" in i for i in issues) and any("999" in i or "quantity" in i for i in issues)


def test_rules_watch_never_overwrites(tmp_path):
    cur = json.loads(open("rules/fy2026_27.json").read())
    new = dict(cur, fy="2027-28", ltcg_exemption_paise=15000000)
    out = propose_rules_update(cur, "text", Fake(json.dumps(new)), tmp_path)
    assert out["diff"].keys() == {"fy", "ltcg_exemption_paise"} and out["requires_human_review"]
    assert (tmp_path / "proposed_2027-28.json").exists()
    bad = dict(new, stcg_rate="3/2")
    try:
        propose_rules_update(cur, "text", Fake(json.dumps(bad)), tmp_path)
        assert False
    except ValueError:
        pass


def test_llm_eval_scoring(rules):
    pos = generate_portfolio(3)
    prof, SALE = TaxProfile(), date(2026, 11, 5)
    W = int(0.3 * sum(p.price * p.total_qty for p in pos))
    opt = brute_force(pos, W, SALE, prof, rules)
    assert "lot 1" in build_prompt(pos, W, SALE, prof)
    assert not score("garbage", pos, W, SALE, prof, rules, opt.tax)["valid_json"]
    # selling only the SECOND FIFO lot of a position is a FIFO violation
    p = pos[0]
    reply = json.dumps({"sells": [{"symbol": p.symbol, "lot": 2, "qty": 1}], "claimed_tax_rupees": 0})
    s = score(reply, pos, W, SALE, prof, rules, opt.tax)
    assert s["valid_json"] and s["fifo_violation"] is True and s["feasible"] is False
