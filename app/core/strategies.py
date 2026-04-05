from __future__ import annotations
import numpy as np


def _leg_payoff(leg: dict, spot: float) -> float:
    """Net payoff (intrinsic minus/plus premium) for one leg at expiry."""
    strike = leg["strike"]
    premium = leg.get("premium", 0.0)
    position = leg["position"]

    if leg["type"] == "call":
        intrinsic = max(spot - strike, 0.0)
    else:
        intrinsic = max(strike - spot, 0.0)

    return (intrinsic - premium) if position == "long" else (-intrinsic + premium)


def _total_payoff(legs: list[dict], spot: float) -> float:
    return sum(_leg_payoff(leg, spot) for leg in legs)


def _total_payoff_vec(legs: list[dict], spots: np.ndarray) -> np.ndarray:
    """Vectorized total payoff for all legs across an array of spot prices."""
    total = np.zeros_like(spots)
    for leg in legs:
        strike = leg["strike"]
        premium = leg.get("premium", 0.0)
        if leg["type"] == "call":
            intrinsic = np.maximum(spots - strike, 0.0)
        else:
            intrinsic = np.maximum(strike - spots, 0.0)
        if leg["position"] == "long":
            total += intrinsic - premium
        else:
            total += -intrinsic + premium
    return total


def identify_strategy(legs: list[dict]) -> str:
    calls = [l for l in legs if l["type"] == "call"]
    puts = [l for l in legs if l["type"] == "put"]
    n = len(legs)

    if n == 1:
        leg = legs[0]
        prefix = "long" if leg["position"] == "long" else "short"
        return f"{prefix}_{leg['type']}"

    if n == 2:
        if len(calls) == 2:
            long_c = next((c for c in calls if c["position"] == "long"), None)
            short_c = next((c for c in calls if c["position"] == "short"), None)
            if long_c and short_c:
                return "bull_call_spread" if long_c["strike"] < short_c["strike"] else "bear_call_spread"

        if len(puts) == 2:
            long_p = next((p for p in puts if p["position"] == "long"), None)
            short_p = next((p for p in puts if p["position"] == "short"), None)
            if long_p and short_p:
                return "bear_put_spread" if long_p["strike"] > short_p["strike"] else "bull_put_spread"

        if len(calls) == 1 and len(puts) == 1:
            c, p = calls[0], puts[0]
            both_long = c["position"] == "long" and p["position"] == "long"
            both_short = c["position"] == "short" and p["position"] == "short"
            same_strike = abs(c["strike"] - p["strike"]) < 1e-9
            if both_long:
                return "long_straddle" if same_strike else "long_strangle"
            if both_short:
                return "short_straddle" if same_strike else "short_strangle"

    if n == 3:
        for legs_subset in [calls, puts]:
            if len(legs_subset) == 3:
                sorted_legs = sorted(legs_subset, key=lambda l: l["strike"])
                positions = [l["position"] for l in sorted_legs]
                if positions == ["long", "short", "long"]:
                    return "butterfly_spread"
                if positions == ["short", "long", "short"]:
                    return "reverse_butterfly"

    if n == 4 and len(calls) == 2 and len(puts) == 2:
        return "iron_condor"

    return "custom"


def analyze_strategy(legs: list[dict], spot: float) -> dict:
    all_strikes = sorted({leg["strike"] for leg in legs})
    lo = max(0.01, min(all_strikes) * 0.4)
    hi = max(all_strikes) * 2.0

    # Dense grid for payoff table and breakeven detection
    grid = np.linspace(lo, hi, 400)
    payoffs = _total_payoff_vec(legs, grid)

    max_p = float(payoffs.max())
    min_p = float(payoffs.min())

    # Check if payoff continues beyond our grid at extremes (unbounded)
    extremes = _total_payoff_vec(legs, np.array([lo / 20.0, hi * 20.0]))
    far_left, far_right = float(extremes[0]), float(extremes[1])
    max_profit: float | None = round(max_p, 4) if (far_right <= max_p + 0.01 and far_left <= max_p + 0.01) else None
    max_loss: float | None = round(min_p, 4) if (far_right >= min_p - 0.01 and far_left >= min_p - 0.01) else None

    # Zero-crossing breakevens (vectorized sign-change detection)
    signs = payoffs[:-1] * payoffs[1:]
    diffs = np.abs(payoffs[1:] - payoffs[:-1])
    crossings = np.where((signs <= 0) & (diffs > 1e-12))[0]
    breakevens: list[float] = []
    for i in crossings:
        y0, y1 = float(payoffs[i]), float(payoffs[i + 1])
        be = float(grid[i]) + (-y0) * (float(grid[i + 1]) - float(grid[i])) / (y1 - y0)
        if not breakevens or abs(be - breakevens[-1]) > 0.05:
            breakevens.append(round(be, 4))

    # 20-point payoff sample for the response
    sample = np.linspace(lo, hi, 20)
    sample_payoffs = _total_payoff_vec(legs, sample)
    payoff_table = [
        {"spot": round(float(s), 2), "value": round(float(v), 4)}
        for s, v in zip(sample, sample_payoffs)
    ]

    return {
        "strategy": identify_strategy(legs),
        "max_profit": max_profit,
        "max_loss": max_loss,
        "breakevens": breakevens,
        "payoff": payoff_table,
    }
