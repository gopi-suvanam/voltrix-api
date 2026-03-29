def option_price_insights(S: float, K: float, sigma: float, vol_input: dict | None = None) -> dict:
    """Generate insights for the option pricing response."""
    insights: dict = {}

    # Moneyness
    ratio = S / K
    if ratio > 1.02:
        insights["moneyness"] = "in_the_money"
    elif ratio < 0.98:
        insights["moneyness"] = "out_of_the_money"
    else:
        insights["moneyness"] = "at_the_money"

    # Vol regime
    if sigma < 0.15:
        insights["vol_regime"] = "low"
    elif sigma < 0.30:
        insights["vol_regime"] = "normal"
    else:
        insights["vol_regime"] = "elevated"

    # Surface skew (only for matrix surfaces)
    if vol_input and vol_input.get("surface_type") == "matrix":
        data = vol_input.get("data", {})
        vol_matrix = data.get("vol_matrix") or []
        if len(vol_matrix) >= 3:
            # Use first maturity column to detect skew across strikes
            col = [row[0] for row in vol_matrix if row]
            if len(col) >= 3:
                left_wing = col[0]
                center = col[len(col) // 2]
                right_wing = col[-1]
                sym_diff = abs(left_wing - right_wing)
                if sym_diff < 0.02 and center < min(left_wing, right_wing) - 0.005:
                    insights["surface_skew"] = "smile_detected"
                elif left_wing > right_wing + 0.02:
                    insights["surface_skew"] = "negative_skew"
                elif right_wing > left_wing + 0.02:
                    insights["surface_skew"] = "positive_skew"
                else:
                    insights["surface_skew"] = "flat"

    return insights


def greeks_insights(delta: float, vega: float, theta: float) -> dict:
    """Generate human-readable interpretation of Greeks values."""
    interpretation: dict = {}

    abs_delta = abs(delta)
    if abs_delta < 0.2:
        interpretation["delta"] = "Low directional exposure"
    elif abs_delta < 0.5:
        interpretation["delta"] = "Moderate directional exposure"
    else:
        interpretation["delta"] = "High directional exposure"

    abs_vega = abs(vega)
    if abs_vega < 0.05:
        interpretation["vega"] = "Low volatility sensitivity"
    elif abs_vega < 0.15:
        interpretation["vega"] = "Moderate volatility sensitivity"
    else:
        interpretation["vega"] = "Highly sensitive to volatility"

    abs_theta = abs(theta)
    if abs_theta < 0.005:
        interpretation["theta"] = "Minimal time decay"
    elif abs_theta < 0.03:
        interpretation["theta"] = "Time decay moderate"
    else:
        interpretation["theta"] = "Significant time decay"

    return interpretation


def vol_insights(vol: float) -> dict:
    """Generate insights for volatility endpoint."""
    if vol < 0.15:
        return {"vol_regime": "low", "relative_level": "below_historical_avg"}
    elif vol < 0.30:
        return {"vol_regime": "normal", "relative_level": "near_historical_avg"}
    else:
        return {"vol_regime": "elevated", "relative_level": "above_historical_avg"}
