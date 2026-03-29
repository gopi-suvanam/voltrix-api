import numpy as np
from scipy.stats import norm
from .pricing import bs_price, bachelier_price


# ---------------------------------------------------------------------------
# Vega helpers (raw, not scaled)
# ---------------------------------------------------------------------------

def _bs_vega(S: float, K: float, T: float, r: float, q: float, sigma: float) -> float:
    if T <= 0 or sigma <= 0:
        return 0.0
    sqrt_T = np.sqrt(T)
    d1 = (np.log(S / K) + (r - q + 0.5 * sigma ** 2) * T) / (sigma * sqrt_T)
    return float(S * np.exp(-q * T) * norm.pdf(d1) * sqrt_T)


def _bachelier_vega(S: float, K: float, T: float, r: float, q: float, sigma: float) -> float:
    if T <= 0 or sigma <= 0:
        return 0.0
    F = S * np.exp((r - q) * T)
    d = (F - K) / (sigma * np.sqrt(T))
    return float(np.exp(-r * T) * np.sqrt(T) * norm.pdf(d))


# ---------------------------------------------------------------------------
# Bisection fallback
# ---------------------------------------------------------------------------

def _bisection_iv(
    market_price: float, S: float, K: float, T: float, r: float, q: float,
    option_type: str, vol_type: str, tol: float, max_iter: int,
) -> tuple[float, int, float, str]:
    price_fn = bs_price if vol_type == "log_normal" else bachelier_price

    lo, hi = 1e-6, 10.0
    p_lo = price_fn(S, K, T, r, q, lo, option_type)
    p_hi = price_fn(S, K, T, r, q, hi, option_type)

    if market_price < p_lo:
        raise ValueError(
            f"Market price {market_price:.4f} is below the minimum attainable price {p_lo:.4f}. "
            "Check inputs or option price."
        )
    if market_price > p_hi:
        raise ValueError(
            f"Market price {market_price:.4f} exceeds maximum attainable price {p_hi:.4f}. "
            "Check inputs or option price."
        )

    for i in range(max_iter):
        mid = (lo + hi) / 2.0
        err = price_fn(S, K, T, r, q, mid, option_type) - market_price
        if abs(err) < tol:
            return mid, i + 1, err, "converged"
        if err > 0:
            hi = mid
        else:
            lo = mid

    mid = (lo + hi) / 2.0
    err = price_fn(S, K, T, r, q, mid, option_type) - market_price
    return mid, max_iter, err, "max_iterations_reached"


# ---------------------------------------------------------------------------
# Implied volatility: Newton-Raphson + bisection fallback
# ---------------------------------------------------------------------------

def implied_vol(
    market_price: float,
    S: float, K: float, T: float, r: float, q: float,
    option_type: str,
    vol_type: str = "log_normal",
    initial_guess: float = 0.2,
    tolerance: float = 1e-6,
    max_iterations: int = 100,
) -> tuple[float, int, float, str]:
    """
    Newton-Raphson implied vol solver with bisection fallback.
    Returns (sigma, iterations, error, status).
    """
    price_fn = bs_price if vol_type == "log_normal" else bachelier_price
    vega_fn = _bs_vega if vol_type == "log_normal" else _bachelier_vega

    sigma = max(initial_guess, 1e-6)

    for i in range(max_iterations):
        p = price_fn(S, K, T, r, q, sigma, option_type)
        err = p - market_price

        if abs(err) < tolerance:
            return sigma, i + 1, err, "converged"

        v = vega_fn(S, K, T, r, q, sigma)
        if abs(v) < 1e-12:
            break  # degenerate vega → switch to bisection

        sigma_new = sigma - err / v
        if sigma_new <= 0 or sigma_new > 20.0:
            break  # out of sensible range → switch to bisection

        sigma = sigma_new

    return _bisection_iv(market_price, S, K, T, r, q, option_type, vol_type, tolerance, max_iterations)


# ---------------------------------------------------------------------------
# Historical volatility
# ---------------------------------------------------------------------------

def historical_vol(
    prices: list[float],
    window: int | None = None,
    annualization_factor: int = 252,
    method: str = "log_returns",
) -> float:
    """Compute annualised historical volatility from a price series."""
    arr = np.array(prices, dtype=np.float64)
    if len(arr) < 2:
        raise ValueError("Need at least 2 prices to compute historical volatility")

    if method == "log_returns":
        returns = np.log(arr[1:] / arr[:-1])
    else:
        returns = np.diff(arr) / arr[:-1]

    if window is not None and 1 < window < len(returns):
        returns = returns[-window:]

    return float(np.std(returns, ddof=1) * np.sqrt(annualization_factor))
