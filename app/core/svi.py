import numpy as np


def svi_implied_vol(
    F: float,
    K: float,
    T: float,
    a: float,
    b: float,
    rho: float,
    m: float,
    sigma: float,
) -> float:
    """
    Raw SVI (Stochastic Volatility Inspired) implied Black-Scholes volatility.

    Gatheral (2004) raw SVI parametrisation:
        w(k) = a + b * (rho*(k - m) + sqrt((k - m)^2 + sigma^2))

    where k = ln(K/F) is log-moneyness and w = implied_var * T (total variance).

    Parameters
    ----------
    F     : forward price
    K     : strike
    T     : time to expiry (years)
    a     : vertical shift of the smile (total-variance level)
    b     : "angle" / breadth parameter (b >= 0)
    rho   : asymmetry / skew parameter (-1 < rho < 1)
    m     : ATM shift in log-moneyness space
    sigma : "width" / curvature parameter (sigma > 0)

    Returns
    -------
    Implied Black-Scholes volatility (float).

    Notes
    -----
    No arbitrage requires a >= 0, b >= 0, |rho| < 1, sigma > 0, and
    a + b*sigma*sqrt(1-rho^2) >= 0. The caller is responsible for supplying
    valid (butterfly-arbitrage-free) parameters.
    """
    if T <= 0:
        raise ValueError("T must be positive")
    if F <= 0 or K <= 0:
        raise ValueError("Forward and strike must be positive")
    if b < 0:
        raise ValueError("b must be non-negative")
    if sigma <= 0:
        raise ValueError("sigma must be positive")

    k = np.log(K / F)
    w = a + b * (rho * (k - m) + np.sqrt((k - m) ** 2 + sigma ** 2))

    if w <= 0:
        raise ValueError(
            f"SVI total variance w={w:.6g} <= 0 at k={k:.4f}. "
            "Check parameters for butterfly-arbitrage-free conditions."
        )

    return float(np.sqrt(w / T))


def svi_implied_vol_batch(
    Fs: np.ndarray,
    Ks: np.ndarray,
    Ts: np.ndarray,
    a: float,
    b: float,
    rho: float,
    m: float,
    sigma: float,
) -> np.ndarray:
    """
    Vectorized raw SVI implied vol for arrays of (F, K, T).
    Returns NaN where total variance w <= 0.
    """
    k = np.log(Ks / Fs)
    w = a + b * (rho * (k - m) + np.sqrt((k - m) ** 2 + sigma ** 2))
    # Clamp negative total variance to a tiny positive to avoid NaN in sqrt
    w_safe = np.maximum(w, 1e-12)
    return np.sqrt(w_safe / Ts)
