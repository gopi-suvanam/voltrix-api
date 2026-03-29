import numpy as np
from scipy.stats import norm
from .pricing import price_option


def bs_greeks_analytic(
    S: float, K: float, T: float, r: float, q: float, sigma: float, option_type: str
) -> dict:
    """Exact analytical Black-Scholes Greeks."""
    sqrt_T = np.sqrt(T)
    d1 = (np.log(S / K) + (r - q + 0.5 * sigma ** 2) * T) / (sigma * sqrt_T)
    d2 = d1 - sigma * sqrt_T

    # Delta
    if option_type == "call":
        delta = float(np.exp(-q * T) * norm.cdf(d1))
    else:
        delta = float(np.exp(-q * T) * (norm.cdf(d1) - 1.0))

    # Gamma (same for call and put)
    gamma = float(np.exp(-q * T) * norm.pdf(d1) / (S * sigma * sqrt_T))

    # Vega per 1% vol change
    vega = float(S * np.exp(-q * T) * norm.pdf(d1) * sqrt_T * 0.01)

    # Theta per calendar day
    common = -S * np.exp(-q * T) * norm.pdf(d1) * sigma / (2.0 * sqrt_T)
    if option_type == "call":
        theta = float(
            (common - r * K * np.exp(-r * T) * norm.cdf(d2)
             + q * S * np.exp(-q * T) * norm.cdf(d1)) / 365.0
        )
    else:
        theta = float(
            (common + r * K * np.exp(-r * T) * norm.cdf(-d2)
             - q * S * np.exp(-q * T) * norm.cdf(-d1)) / 365.0
        )

    # Rho per 1% rate change
    if option_type == "call":
        rho = float(K * T * np.exp(-r * T) * norm.cdf(d2) * 0.01)
    else:
        rho = float(-K * T * np.exp(-r * T) * norm.cdf(-d2) * 0.01)

    return {
        "delta": round(delta, 6),
        "gamma": round(gamma, 6),
        "vega": round(vega, 6),
        "theta": round(theta, 6),
        "rho": round(rho, 6),
    }


def numerical_greeks(
    S: float, K: float, T: float, r: float, q: float, sigma: float,
    option_type: str, model: str,
    bump_size: float = 0.01,
    beta: float = 1.0,
    num_simulations: int = 10000,
    seed: int | None = None,
) -> dict:
    """
    Central-difference numerical Greeks.
    Uses common random numbers (same seed per bump) to reduce MC variance.
    """
    def price(s, k, t, r_, q_, sig):
        return price_option(model, option_type, s, k, t, r_, q_, sig,
                            beta=beta, num_simulations=num_simulations, seed=seed)

    h_s = bump_size * S       # spot bump
    h_sig = bump_size         # vol bump
    h_r = bump_size           # rate bump

    p_base = price(S, K, T, r, q, sigma)

    # Delta + Gamma (central diff on spot)
    p_sup = price(S + h_s, K, T, r, q, sigma)
    p_sdn = price(S - h_s, K, T, r, q, sigma)
    delta = (p_sup - p_sdn) / (2.0 * h_s)
    gamma = (p_sup - 2.0 * p_base + p_sdn) / (h_s ** 2)

    # Vega (central diff on sigma, result per 1% change)
    p_vup = price(S, K, T, r, q, sigma + h_sig)
    p_vdn = price(S, K, T, r, q, sigma - h_sig)
    vega = (p_vup - p_vdn) / (2.0 * h_sig) * 0.01

    # Theta (forward diff: value of 1 day passing = T decreases by 1/365)
    h_t = 1.0 / 365.0
    p_t1 = price(S, K, max(T - h_t, 1e-6), r, q, sigma)
    theta = p_t1 - p_base  # per day (typically negative)

    # Rho (central diff on rate, result per 1% change)
    p_rup = price(S, K, T, r + h_r, q, sigma)
    p_rdn = price(S, K, T, r - h_r, q, sigma)
    rho = (p_rup - p_rdn) / (2.0 * h_r) * 0.01

    return {
        "delta": round(float(delta), 6),
        "gamma": round(float(gamma), 6),
        "vega": round(float(vega), 6),
        "theta": round(float(theta), 6),
        "rho": round(float(rho), 6),
    }


def compute_greeks(
    model: str,
    option_type: str,
    S: float, K: float, T: float, r: float, q: float, sigma: float,
    method: str = "analytic",
    bump_size: float = 0.01,
    beta: float = 1.0,
    num_simulations: int = 10000,
    seed: int | None = None,
) -> dict:
    """Route to analytic (BS only) or numerical Greeks."""
    if method == "analytic" and model == "black_scholes":
        return bs_greeks_analytic(S, K, T, r, q, sigma, option_type)
    return numerical_greeks(S, K, T, r, q, sigma, option_type, model,
                            bump_size=bump_size, beta=beta,
                            num_simulations=num_simulations, seed=seed)
