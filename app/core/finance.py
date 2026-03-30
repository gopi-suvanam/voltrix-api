from __future__ import annotations
from datetime import date
from .day_count import year_fraction

_FREQ_PER_YEAR: dict[str, int] = {
    "weekly": 52,
    "monthly": 12,
    "quarterly": 4,
    "semi_annual": 2,
    "annual": 1,
}


def compute_npv(
    settlement: date,
    cashflows: list[dict],
    discount_rate: float,
    day_count: str = "ACT/365",
) -> dict:
    """Discount each cashflow back to settlement_date and sum."""
    npv = 0.0
    discount_factors: list[float] = []
    year_fractions: list[float] = []

    for cf in cashflows:
        t = year_fraction(settlement, cf["date"], day_count)
        df = (1.0 + discount_rate) ** (-t) if t > 0 else 1.0
        npv += cf["amount"] * df
        discount_factors.append(round(df, 8))
        year_fractions.append(round(t, 8))

    return {
        "npv": round(npv, 6),
        "details": {
            "discount_factors": discount_factors,
            "year_fractions": year_fractions,
        },
    }


def compute_pmt(
    principal: float,
    rate: float,
    start_date: date,
    end_date: date,
    frequency: str,
) -> dict:
    """Compute the fixed periodic payment for a fully-amortising loan."""
    if frequency not in _FREQ_PER_YEAR:
        raise ValueError(
            f"Unknown frequency: '{frequency}'. Supported: {list(_FREQ_PER_YEAR.keys())}"
        )

    periods_per_year = _FREQ_PER_YEAR[frequency]
    total_days = (end_date - start_date).days

    if total_days <= 0:
        raise ValueError("end_date must be after start_date")

    total_years = total_days / 365.25
    n = max(1, round(total_years * periods_per_year))
    r = rate / periods_per_year

    if abs(r) < 1e-12:
        payment = principal / n
    else:
        payment = principal * r / (1.0 - (1.0 + r) ** (-n))

    total_payment = payment * n
    interest_paid = total_payment - principal

    return {
        "payment": round(payment, 6),
        "num_periods": n,
        "total_payment": round(total_payment, 6),
        "interest_paid": round(interest_paid, 6),
    }
