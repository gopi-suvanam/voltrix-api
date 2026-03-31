import numpy as np
from scipy.stats import norm
from .heston import heston_price, heston_mc_price


def bs_price(S: float, K: float, T: float, r: float, q: float, sigma: float, option_type: str) -> float:
    """Black-Scholes (log-normal) European option price."""
    if T <= 0:
        return max(S - K, 0.0) if option_type == "call" else max(K - S, 0.0)
    if sigma <= 0:
        raise ValueError("sigma must be positive for Black-Scholes")

    sqrt_T = np.sqrt(T)
    d1 = (np.log(S / K) + (r - q + 0.5 * sigma ** 2) * T) / (sigma * sqrt_T)
    d2 = d1 - sigma * sqrt_T

    if option_type == "call":
        return float(S * np.exp(-q * T) * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2))
    else:
        return float(K * np.exp(-r * T) * norm.cdf(-d2) - S * np.exp(-q * T) * norm.cdf(-d1))


def bachelier_price(S: float, K: float, T: float, r: float, q: float, sigma: float, option_type: str) -> float:
    """Bachelier (normal) European option price."""
    if T <= 0:
        intrinsic = max(S - K, 0.0) if option_type == "call" else max(K - S, 0.0)
        return intrinsic * np.exp(-r * T)
    if sigma <= 0:
        raise ValueError("sigma must be positive for Bachelier model")

    F = S * np.exp((r - q) * T)
    stddev = sigma * np.sqrt(T)
    d = (F - K) / stddev

    if option_type == "call":
        return float(np.exp(-r * T) * ((F - K) * norm.cdf(d) + stddev * norm.pdf(d)))
    else:
        return float(np.exp(-r * T) * ((K - F) * norm.cdf(-d) + stddev * norm.pdf(d)))


def mc_price(
    S: float,
    K: float,
    T: float,
    r: float,
    q: float,
    sigma: float,
    option_type: str,
    beta: float = 1.0,
    num_simulations: int = 10000,
    seed: int | None = None,
    num_steps: int = 252,
) -> float:
    """Monte Carlo option pricing. beta=1 uses exact GBM; other beta uses CEV time-stepping."""
    rng = np.random.default_rng(seed)

    # Exact GBM simulation (no discretisation error, much faster)
    if abs(beta - 1.0) < 1e-9:
        Z = rng.standard_normal(num_simulations)
        ST = S * np.exp((r - q - 0.5 * sigma ** 2) * T + sigma * np.sqrt(T) * Z)
    else:
        # CEV: dS = (r-q)*S*dt + sigma*S^beta*sqrt(dt)*Z
        dt = T / num_steps
        sqrt_dt = np.sqrt(dt)
        Z_all = rng.standard_normal((num_steps, num_simulations))
        paths = np.full(num_simulations, float(S))
        for i in range(num_steps):
            drift = (r - q) * paths * dt
            diffusion = sigma * (np.maximum(paths, 0.0) ** beta) * sqrt_dt * Z_all[i]
            paths = np.maximum(paths + drift + diffusion, 0.0)
        ST = paths

    if option_type == "call":
        payoffs = np.maximum(ST - K, 0.0)
    else:
        payoffs = np.maximum(K - ST, 0.0)

    return float(np.exp(-r * T) * np.mean(payoffs))


def price_option(
    model: str,
    option_type: str,
    S: float,
    K: float,
    T: float,
    r: float,
    q: float,
    sigma: float,
    beta: float = 1.0,
    num_simulations: int = 10000,
    seed: int | None = None,
    heston_params: dict | None = None,
) -> float:
    """
    Dispatch to the appropriate pricing model.

    For model='heston', heston_params must be provided:
        {"v0", "kappa", "theta", "sigma_v", "rho"}
    Set heston_params["use_mc"]=True to use Monte Carlo instead of semi-analytic.
    """
    if model == "black_scholes":
        return bs_price(S, K, T, r, q, sigma, option_type)
    elif model == "bachelier":
        return bachelier_price(S, K, T, r, q, sigma, option_type)
    elif model == "cev":
        return mc_price(S, K, T, r, q, sigma, option_type, beta=beta,
                        num_simulations=num_simulations, seed=seed)
    elif model == "monte_carlo":
        return mc_price(S, K, T, r, q, sigma, option_type, beta=1.0,
                        num_simulations=num_simulations, seed=seed)
    elif model == "heston":
        if not heston_params:
            raise ValueError("heston_params dict required for model='heston'")
        hp = heston_params
        if hp.get("use_mc", False):
            return heston_mc_price(
                S=S, K=K, T=T, r=r, q=q,
                v0=hp["v0"], kappa=hp["kappa"], theta=hp["theta"],
                sigma_v=hp["sigma_v"], rho=hp["rho"],
                option_type=option_type,
                num_simulations=num_simulations,
                seed=seed,
            )
        return heston_price(
            S=S, K=K, T=T, r=r, q=q,
            v0=hp["v0"], kappa=hp["kappa"], theta=hp["theta"],
            sigma_v=hp["sigma_v"], rho=hp["rho"],
            option_type=option_type,
        )
    else:
        raise ValueError(f"Unknown model: {model}")
