"""NSE trading calendar. Data lives in calendars/nse_<year>.json and must be refreshed every year.
A sale date decides short- vs long-term, so a non-trading date can silently change the tax."""
import json
from datetime import date, timedelta
from pathlib import Path


class TradingCalendar:
    def __init__(self, years: dict):
        self.years = years          # {year: {"holidays": {iso: name}, "special_sessions": {iso: name}}}

    @classmethod
    def load(cls, directory):
        years = {}
        for f in sorted(Path(directory).glob("nse_*.json")):
            d = json.loads(f.read_text())
            years[int(d["year"])] = {"holidays": d.get("holidays", {}), "special_sessions": d.get("special_sessions", {})}
        return cls(years)

    def covers(self, d: date) -> bool:
        return d.year in self.years

    def holiday_name(self, d: date):
        return self.years.get(d.year, {}).get("holidays", {}).get(d.isoformat())

    def special_session(self, d: date):
        return self.years.get(d.year, {}).get("special_sessions", {}).get(d.isoformat())

    def is_trading_day(self, d: date) -> bool:
        """Regular full session. Special weekend sessions do not count when rolling forward."""
        return d.weekday() < 5 and self.holiday_name(d) is None

    def resolve(self, d: date):
        """Returns (effective sale date, warnings). Rolls forward to the next regular trading day."""
        warnings = []
        if self.special_session(d):
            return d, [f"{d} is a special session ({self.special_session(d)}). Hours are limited; confirm your broker allows trading."]
        cur = d
        while not self.is_trading_day(cur):
            cur += timedelta(days=1)
        if cur != d:
            reason = self.holiday_name(d) or d.strftime("%A")
            warnings.append(f"{d} is not a trading day ({reason}). The plan uses {cur}, the next trading day.")
        if not self.covers(cur):
            warnings.append(f"No NSE holiday calendar for {cur.year}: weekends are skipped but exchange holidays are NOT checked.")
        return cur, warnings
