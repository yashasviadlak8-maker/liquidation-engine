"""Deterministic broker-file ingestion: tradebook CSV -> FIFO lots -> positions.

Assumed column names (Zerodha-style tradebook; matched case-insensitively):
symbol, trade_date, trade_type (buy/sell), quantity, price. Verify against real exports.
Not handled (reported as issues): splits, bonuses, mergers, off-market transfers.
"""
import csv
import io
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP

from engine.models import Lot, Position

DATE_FORMATS = ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%d-%b-%Y")
REQUIRED = ("symbol", "trade_date", "trade_type", "quantity", "price")


def to_paise(x) -> int:
    return int((Decimal(str(x).replace(",", "").strip()) * 100).to_integral_value(ROUND_HALF_UP))


def parse_date(s: str) -> date:
    s = s.strip()[:11].strip() if len(s.strip()) > 10 and s.strip()[10] in " T" else s.strip()
    for f in DATE_FORMATS:
        try:
            return datetime.strptime(s, f).date()
        except ValueError:
            pass
    raise ValueError(f"unrecognised date {s!r}")


def parse_tradebook(csv_text: str):
    """Returns (lots_by_symbol, last_price_paise, issues). Sells consume the oldest lots first."""
    reader = csv.DictReader(io.StringIO(csv_text))
    reader.fieldnames = [h.strip().lower() for h in (reader.fieldnames or [])]
    missing = [c for c in REQUIRED if c not in reader.fieldnames]
    if missing:
        raise ValueError(f"missing columns: {', '.join(missing)}")
    rows = []
    for n, r in enumerate(reader):
        rows.append((parse_date(r["trade_date"]), n, r))
    rows.sort(key=lambda t: (t[0], t[1]))
    lots, last, issues = {}, {}, []
    for d, _, r in rows:
        sym, kind = r["symbol"].strip().upper(), r["trade_type"].strip().lower()
        qty, price = int(Decimal(r["quantity"].strip())), to_paise(r["price"])
        last[sym] = price
        book = lots.setdefault(sym, [])
        if kind == "buy":
            book.append([d, qty, price])
        elif kind == "sell":
            left = qty
            while left and book:
                take = min(left, book[0][1])
                book[0][1] -= take
                left -= take
                if book[0][1] == 0:
                    book.pop(0)
            if left:
                issues.append(f"{sym}: sold {left} more shares than the file's buys cover "
                              f"(earlier buys, bonus or split missing?)")
        else:
            issues.append(f"{sym}: ignored trade type {kind!r} on {d}")
    lots = {s: [Lot(d, q, c) for d, q, c in b if q > 0] for s, b in lots.items()}
    return {s: b for s, b in lots.items() if b}, last, issues


def build_positions(lots_by_symbol, last_price, prices=None, account="A"):
    """prices: {symbol: paise}. Missing symbols fall back to the last traded price (flagged)."""
    prices, issues, out = prices or {}, [], []
    for sym, lots in sorted(lots_by_symbol.items()):
        if sym in prices:
            price = prices[sym]
        else:
            price = last_price[sym]
            issues.append(f"{sym}: using last traded price; enter the live price before planning")
        out.append(Position(account, sym, price, tuple(lots)))
    return out, issues


def reconcile(lots_by_symbol, holdings: dict):
    """Compare replayed quantities with the demat holdings summary ({symbol: qty})."""
    issues = []
    for sym in sorted(set(lots_by_symbol) | set(holdings)):
        have = sum(l.qty for l in lots_by_symbol.get(sym, []))
        if have != holdings.get(sym, 0):
            issues.append(f"{sym}: tradebook gives {have} shares but holdings show {holdings.get(sym, 0)}")
    return issues
