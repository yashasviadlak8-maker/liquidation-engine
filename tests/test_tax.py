from engine.tax import compute_tax, incremental_tax, TaxProfile

R = 100


def test_short_term_only(rules):
    # 1,00,000 gain * 20% = 20,000; +4% cess = 20,800
    assert compute_tax(100000 * R, 0, rules).tax == 20800 * R


def test_long_term_above_exemption(rules):
    # (2,00,000 - 1,25,000) * 12.5% = 9,375; *1.04 = 9,750
    assert compute_tax(0, 200000 * R, rules).tax == 9750 * R


def test_long_term_inside_exemption(rules):
    r = compute_tax(0, 100000 * R, rules)
    assert r.tax == 0 and r.exemption_used == 100000 * R


def test_st_loss_offsets_lt_gain(rules):
    # LT 2,00,000 - 30,000 = 1,70,000; taxable 45,000 -> 5,625 -> 5,850
    assert compute_tax(-30000 * R, 200000 * R, rules).tax == 5850 * R


def test_lt_loss_cannot_offset_st_gain(rules):
    r = compute_tax(100000 * R, -30000 * R, rules)
    assert r.tax == 20800 * R
    assert r.carry_lt_loss == 30000 * R


def test_brought_forward_lt_loss(rules):
    # LT 2,00,000 - 50,000 b/f = 1,50,000; taxable 25,000 -> 3,125 -> 3,250
    assert compute_tax(0, 200000 * R, rules, bf_lt_loss=50000 * R).tax == 3250 * R


def test_incremental_uses_exemption_already_consumed(rules):
    prof = TaxProfile(ytd_lt=100000 * R)
    inc, _ = incremental_tax(0, 100000 * R, prof, rules)
    assert inc == 9750 * R   # only 25,000 of the exemption was left


def test_rounding_to_paise(rules):
    # 33.33 rupees ST gain: 3333 * 0.2 * 1.04 = 693.264 paise -> 693
    assert compute_tax(3333, 0, rules).tax == 693
