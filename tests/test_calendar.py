from datetime import date
import pytest
from engine.calendar import TradingCalendar
from engine.baselines import losers_first
from engine.models import Lot, Position
from engine.solver import solve
from engine.tax import TaxProfile
from fastapi.testclient import TestClient
from api.main import app

CAL = TradingCalendar.load("calendars")
R = 100


def test_regular_day_unchanged():
    assert CAL.resolve(date(2026, 11, 5)) == (date(2026, 11, 5), [])


def test_weekend_rolls_to_monday():
    d, w = CAL.resolve(date(2026, 11, 7))                  # Saturday
    assert d == date(2026, 11, 9) and "Saturday" in w[0]


def test_holiday_rolls_forward_and_names_it():
    d, w = CAL.resolve(date(2026, 11, 10))                 # Diwali-Balipratipada
    assert d == date(2026, 11, 11) and "Diwali-Balipratipada" in w[0]


def test_holiday_then_weekend_chain():
    assert CAL.resolve(date(2026, 12, 25))[0] == date(2026, 12, 28)   # Christmas Fri, then Sat+Sun


def test_special_sunday_session_accepted_with_warning_but_not_used_for_rolling():
    d, w = CAL.resolve(date(2026, 11, 8))
    assert d == date(2026, 11, 8) and "special session" in w[0]
    assert CAL.resolve(date(2026, 11, 7))[0] == date(2026, 11, 9)     # Saturday skips the Muhurat Sunday


def test_uncovered_year_warns_but_still_skips_weekends():
    d, w = CAL.resolve(date(2027, 3, 13))                  # Saturday, no 2027 calendar
    assert d == date(2027, 3, 15) and any("NOT checked" in x for x in w)
    assert CAL.resolve(date(2027, 3, 10))[0] == date(2027, 3, 10)


def test_boundary_changes_tax_through_the_api():
    """Lot bought Fri 2025-11-07. Entering Sat 2026-11-07 would be exactly 12 months (short-term),
    but the real trade happens Mon 2026-11-09 (long-term). The planner must use the real date."""
    pos = [{"symbol": "ZZZ", "price": 2000, "lots": [{"buy_date": "2025-11-07", "qty": 100, "unit_cost": 1000}]}]
    c = TestClient(app)
    a = c.post("/api/plan", json={"positions": pos, "amount": 200000, "sale_date": "2026-11-07"}).json()
    assert a["sale_date_used"] == "2026-11-09" and a["tax"] == 0 and a["calendar_warnings"]
    b = c.post("/api/plan", json={"positions": pos, "amount": 200000, "sale_date": "2026-11-06"}).json()
    assert b["sale_date_used"] == "2026-11-06" and b["tax"] == 20800      # Friday: still short-term


def test_zero_tax_ties_prefer_fewer_positions(rules):
    buy = date(2026, 6, 1)
    pos = [Position("A", f"P{i}", 1000 * R, (Lot(buy, 100, 1000 * R),)) for i in range(4)]   # zero gain everywhere
    r = solve(pos, 100000 * R, date(2026, 11, 5), TaxProfile(), rules)
    assert r.tax == 0 and r.positions_sold == 1 and r.proceeds == 100000 * R


def test_losers_first_sells_underwater_first(rules):
    buy = date(2026, 6, 1)
    win = Position("A", "WIN", 1000 * R, (Lot(buy, 100, 500 * R),))
    lose = Position("A", "LOSE", 1000 * R, (Lot(buy, 100, 1500 * R),))
    assert losers_first([win, lose], 50000 * R) == {("A", "WIN"): 0, ("A", "LOSE"): 50}
