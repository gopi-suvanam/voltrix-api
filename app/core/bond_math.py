from __future__ import annotations
from datetime import date
from .day_count import add_months, year_fraction

_FREQ_MONTHS: dict[str, int] = {
    "annual": 12,
    "semi_annual": 6,
    "quarterly": 3,
    "monthly": 1,
}

_FREQ_PER_YEAR: dict[str, int] = {
    "annual": 1,
    "semi_annual": 2,
    "quarterly": 4,
    "monthly": 12,
}


def _coupon_dates(settlement: date, maturity: date, freq: str) -> list[date]:
    """All coupon dates strictly after settlement, up to and including maturity."""
    months = _FREQ_MONTHS[freq]
    dates: list[date] = []
    d = maturity
    while d > settlement:
        dates.append(d)
        d = add_months(d, -months)
    return sorted(dates)


def _last_coupon_date(settlement: date, maturity: date, freq: str) -> date:
    """Most recent coupon date on or before settlement."""
    months = _FREQ_MONTHS[freq]
    d = maturity
    while d > settlement:
        d = add_months(d, -months)
    return d


def accrued_interest(
    settlement: date,
    maturity: date,
    coupon_rate: float,
    face_value: float,
    freq: str,
    day_count: str = "30/360",
) -> float:
    """Compute accrued interest from last coupon date to settlement."""
    freq_per_year = _FREQ_PER_YEAR[freq]
    coupon_per_period = face_value * coupon_rate / freq_per_year
    last_cpn = _last_coupon_date(settlement, maturity, freq)
    next_cpn = add_months(last_cpn, _FREQ_MONTHS[freq])
    period_yf = year_fraction(last_cpn, next_cpn, day_count)
    elapsed_yf = year_fraction(last_cpn, settlement, day_count)
    if period_yf <= 0:
        return 0.0
    return coupon_per_period * (elapsed_yf / period_yf)


def _dirty_price(
    settlement: date,
    maturity: date,
    coupon_rate: float,
    face_value: float,
    freq: str,
    ytm: float,
    day_count: str,
) -> float:
    """Dirty (full) bond price at the given yield-to-maturity."""
    freq_per_year = _FREQ_PER_YEAR[freq]
    coupon_per_period = face_value * coupon_rate / freq_per_year
    cpn_dates = _coupon_dates(settlement, maturity, freq)

    price = 0.0
    for d in cpn_dates:
        t = year_fraction(settlement, d, day_count)
        cf = coupon_per_period + (face_value if d == maturity else 0.0)
        df = (1.0 + ytm / freq_per_year) ** (-t * freq_per_year)
        price += cf * df
    return price


def bond_price(
    settlement: date,
    maturity: date,
    coupon_rate: float,
    face_value: float,
    freq: str,
    ytm: float,
    day_count: str = "30/360",
) -> dict:
    """Return dirty price, accrued interest, and clean price."""
    dirty = _dirty_price(settlement, maturity, coupon_rate, face_value, freq, ytm, day_count)
    ai = accrued_interest(settlement, maturity, coupon_rate, face_value, freq, day_count)
    clean = dirty - ai
    return {
        "price": round(dirty, 6),
        "accrued_interest": round(ai, 6),
        "clean_price": round(clean, 6),
    }


def solve_yield(
    clean_price: float,
    settlement: date,
    maturity: date,
    coupon_rate: float,
    face_value: float,
    freq: str,
    day_count: str = "30/360",
    initial_guess: float = 0.05,
    tolerance: float = 1e-8,
    max_iterations: int = 100,
) -> tuple[float, int, str]:
    """Newton-Raphson YTM solver. Returns (ytm, iterations, status)."""
    ai = accrued_interest(settlement, maturity, coupon_rate, face_value, freq, day_count)
    target_dirty = clean_price + ai

    ytm = initial_guess

    for i in range(max_iterations):
        p = _dirty_price(settlement, maturity, coupon_rate, face_value, freq, ytm, day_count)
        err = p - target_dirty
        if abs(err) < tolerance:
            return ytm, i + 1, "converged"

        dy = 1e-6
        p_up = _dirty_price(settlement, maturity, coupon_rate, face_value, freq, ytm + dy, day_count)
        p_dn = _dirty_price(settlement, maturity, coupon_rate, face_value, freq, ytm - dy, day_count)
        dpdytm = (p_up - p_dn) / (2.0 * dy)

        if abs(dpdytm) < 1e-14:
            break

        ytm = max(ytm - err / dpdytm, -0.9999)

    return ytm, max_iterations, "max_iterations_reached"


def duration_convexity(
    settlement: date,
    maturity: date,
    coupon_rate: float,
    face_value: float,
    freq: str,
    ytm: float,
    dirty_price: float,
    day_count: str = "30/360",
) -> dict:
    """Compute Macaulay duration, modified duration, and convexity."""
    freq_per_year = _FREQ_PER_YEAR[freq]
    coupon_per_period = face_value * coupon_rate / freq_per_year
    cpn_dates = _coupon_dates(settlement, maturity, freq)

    mac_num = 0.0
    convex_num = 0.0

    for d in cpn_dates:
        t = year_fraction(settlement, d, day_count)
        cf = coupon_per_period + (face_value if d == maturity else 0.0)
        df = (1.0 + ytm / freq_per_year) ** (-t * freq_per_year)
        pv = cf * df
        mac_num += t * pv
        convex_num += t * (t + 1.0 / freq_per_year) * pv

    macaulay = mac_num / dirty_price
    one_plus_y = 1.0 + ytm / freq_per_year
    modified = macaulay / one_plus_y
    convexity = convex_num / (dirty_price * one_plus_y ** 2)

    return {
        "duration": round(macaulay, 6),
        "modified_duration": round(modified, 6),
        "convexity": round(convexity, 6),
    }
