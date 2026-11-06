"""Capital-gains tax for listed equity, one FY. Integer paise, exact fractions."""
from dataclasses import dataclass
from math import floor
from fractions import Fraction

from .rules import Rules


@dataclass(frozen=True)
class TaxProfile:
    ytd_st: int = 0        # short-term gain already realised this FY (paise)
    ytd_lt: int = 0
    bf_st_loss: int = 0    # brought-forward losses (positive numbers)
    bf_lt_loss: int = 0


@dataclass(frozen=True)
class TaxResult:
    tax: int
    taxable_st: int
    taxable_lt: int
    exemption_used: int
    carry_st_loss: int
    carry_lt_loss: int


def _round(x: Fraction) -> int:
    return floor(x + Fraction(1, 2))


def compute_tax(st: int, lt: int, rules: Rules, bf_st_loss: int = 0, bf_lt_loss: int = 0) -> TaxResult:
    # Current-year set-off: ST loss may offset LT gain; LT loss may NOT offset ST gain.
    if st < 0 and lt > 0:
        used = min(-st, lt)
        st += used
        lt -= used
    # Brought-forward: ST losses vs ST then LT gains; LT losses vs LT gains only.
    if bf_st_loss > 0 and st > 0:
        u = min(bf_st_loss, st); st -= u; bf_st_loss -= u
    if bf_st_loss > 0 and lt > 0:
        u = min(bf_st_loss, lt); lt -= u; bf_st_loss -= u
    if bf_lt_loss > 0 and lt > 0:
        u = min(bf_lt_loss, lt); lt -= u; bf_lt_loss -= u

    taxable_st = max(st, 0)
    lt_pos = max(lt, 0)
    ex = min(lt_pos, rules.ltcg_exemption)
    taxable_lt = lt_pos - ex
    base = rules.stcg_rate * taxable_st + rules.ltcg_rate * taxable_lt
    tax = _round(base * (1 + rules.cess_rate))
    return TaxResult(tax, taxable_st, taxable_lt, ex,
                     carry_st_loss=max(-st, 0) + bf_st_loss,
                     carry_lt_loss=max(-lt, 0) + bf_lt_loss)


def incremental_tax(st: int, lt: int, profile: TaxProfile, rules: Rules):
    """Tax caused by a withdrawal on top of what the client already realised this FY."""
    before = compute_tax(profile.ytd_st, profile.ytd_lt, rules, profile.bf_st_loss, profile.bf_lt_loss)
    after = compute_tax(profile.ytd_st + st, profile.ytd_lt + lt, rules, profile.bf_st_loss, profile.bf_lt_loss)
    return after.tax - before.tax, after
