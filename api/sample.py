"""Sample portfolio from the user's screenshot. Buy dates are ASSUMED (the screenshot has none)."""
from datetime import date, timedelta

_SALE = date(2026, 11, 5)
_ROWS = [("AVENUE SUPERMARTS", 1401.30, 75, 1250, 18), ("AVENUE SUPERMARTS", 1401.30, 50, 1326, 6),
         ("DEWAN HOUSING", 540.30, 320, 540.94, 14), ("KRBL", 456.50, 150, 600, 20), ("KRBL", 456.50, 120, 514.59, 5),
         ("GRUH FINANCE", 597, 200, 525, 30), ("FEDERAL BANK", 93.5, 1100, 100, 9), ("KAJARIA CERAMIC", 571.55, 170, 625, 16),
         ("AJANTA PHARMA", 1395.40, 65, 1400, 11), ("TTK PRESTIGE", 6342.15, 10, 7000, 25), ("NILKAMAL", 1620.65, 20, 1600, 3),
         ("HSIL", 395.85, 70, 475, 13), ("VAKRANGEE", 180.40, 150, 300, 8), ("CAN FIN HOMES", 439.30, 35, 520, 22)]


def sample_positions():
    out = {}
    for sym, price, qty, cost, months in _ROWS:
        pos = out.setdefault(sym, {"account": "A", "symbol": sym, "price": price, "lots": []})
        pos["lots"].append({"buy_date": (_SALE - timedelta(days=int(months * 30.4))).isoformat(), "qty": qty, "unit_cost": cost})
    return list(out.values())
