from __future__ import annotations
import calendar
from datetime import date


def add_months(d: date, months: int) -> date:
    """Add a whole number of months to a date, clamping to end-of-month."""
    total_months = d.month - 1 + months
    year = d.year + total_months // 12
    month = total_months % 12 + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def year_fraction(start: date, end: date, convention: str = "ACT/365") -> float:
    """Compute the year fraction between two dates using the specified convention."""
    if end <= start:
        return 0.0

    conv = convention.upper().replace(" ", "").replace("-", "")

    if conv in ("ACT/365", "ACT/365F"):
        return (end - start).days / 365.0

    if conv == "ACT/360":
        return (end - start).days / 360.0

    if conv == "30/360":
        y1, m1, d1 = start.year, start.month, start.day
        y2, m2, d2 = end.year, end.month, end.day
        # 30/360 US bond basis (ISMA)
        if d1 == 31:
            d1 = 30
        if d2 == 31 and d1 == 30:
            d2 = 30
        days = 360 * (y2 - y1) + 30 * (m2 - m1) + (d2 - d1)
        return days / 360.0

    if conv in ("ACT/ACT", "ACT/ACTISDA"):
        if start.year == end.year:
            days_in_year = 366 if calendar.isleap(start.year) else 365
            return (end - start).days / days_in_year
        result = 0.0
        current = start
        while current.year < end.year:
            next_year = date(current.year + 1, 1, 1)
            days_in_year = 366 if calendar.isleap(current.year) else 365
            result += (next_year - current).days / days_in_year
            current = next_year
        days_in_year = 366 if calendar.isleap(end.year) else 365
        result += (end - current).days / days_in_year
        return result

    raise ValueError(
        f"Unknown day count convention: '{convention}'. "
        "Supported: ACT/365, ACT/360, 30/360, ACT/ACT"
    )
