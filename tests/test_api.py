from fastapi.testclient import TestClient
from api.main import app

c = TestClient(app)


def test_health_and_index():
    assert c.get("/api/health").json()["ok"]
    assert "Withdrawal" in c.get("/").text


def test_sample_plan_end_to_end():
    pos = c.get("/api/sample").json()["positions"]
    r = c.post("/api/plan", json={"positions": pos, "amount": 250000})
    assert r.status_code == 200
    d = r.json()
    assert d["tax_optimal"] and d["proceeds"] >= 250000
    assert d["tax"] <= d["baselines"]["pro_rata"]["tax"]
    assert d["explanation"] and d["disclaimer"]


def test_plan_constraints_and_errors():
    pos = c.get("/api/sample").json()["positions"]
    r = c.post("/api/plan", json={"positions": pos, "amount": 250000, "exclude": ["federal bank"], "max_positions": 4})
    d = r.json()
    assert all(s["symbol"] != "FEDERAL BANK" for s in d["sells"]) and len(d["sells"]) <= 4
    assert c.post("/api/plan", json={"positions": pos, "amount": 10**9}).status_code == 422


def test_ingest_and_parse_request():
    csv = "symbol,trade_date,trade_type,quantity,price\nABC,2025-01-10,buy,10,100\n"
    r = c.post("/api/ingest", json={"csv_text": csv, "prices": {"ABC": 120}}).json()
    assert r["positions"][0]["price"] == 120 and not r["issues"]
    assert c.post("/api/ingest", json={"csv_text": "a,b\n1,2"}).status_code == 422
    p = c.post("/api/parse-request", json={"text": "need 2 lakh, avoid KRBL", "symbols": ["KRBL"]}).json()
    assert p["constraints"]["amount_rupees"] == 200000 and p["constraints"]["exclude"] == ["KRBL"]
