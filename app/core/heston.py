import numpy as np
from scipy import integrate


# ── Semi-analytic (characteristic function) ───────────────────────────────────

def _heston_cf_integrand(phi: float, S, K, T, r, q, v0, kappa, theta, sigma_v, rho, j: int) -> float:
    """
    Heston (1993) characteristic function integrand for P1 (j=1) or P2 (j=2).

    P_j = 0.5 + (1/π) * ∫₀^∞  Re[ exp(-i·φ·ln K) · f_j(φ) / (i·φ) ] dφ

    where f_j(φ) = exp(C_j + D_j·v₀ + i·φ·ln(F))
    and F = S·exp((r-q)·T) is the forward.
    """
    i = 1j
    ln_F = np.log(S) + (r - q) * T

    if j == 1:
        u = 0.5
        b = kappa - rho * sigma_v
    else:
        u = -0.5
        b = kappa

    a = kappa * theta

    d = np.sqrt((rho * sigma_v * i * phi - b) ** 2
                - sigma_v ** 2 * (2.0 * u * i * phi - phi ** 2))

    # Albrecher et al. (2007): choose branch so that Re(d) >= 0 ─────────────
    if d.real < 0:
        d = -d

    g = (b - rho * sigma_v * i * phi + d) / (b - rho * sigma_v * i * phi - d)

    exp_dT = np.exp(d * T)

    # Avoid log(0) when g·exp(dT) ≈ 1
    denom_log = 1.0 - g * exp_dT
    denom_D   = 1.0 - g * exp_dT

    C = (r - q) * i * phi * T + a / sigma_v ** 2 * (
        (b - rho * sigma_v * i * phi + d) * T
        - 2.0 * np.log(denom_log / (1.0 - g))
    )
    D = (b - rho * sigma_v * i * phi + d) / sigma_v ** 2 * (
        (1.0 - exp_dT) / denom_D
    )

    f_j = np.exp(C + D * v0 + i * phi * ln_F)

    return float(np.real(np.exp(-i * phi * np.log(K)) * f_j / (i * phi)))


def heston_price(
    S: float,
    K: float,
    T: float,
    r: float,
    q: float,
    v0: float,
    kappa: float,
    theta: float,
    sigma_v: float,
    rho: float,
    option_type: str = "call",
) -> float:
    """
    Heston (1993) semi-analytic European option price.

    Model:
        dS = (r-q) S dt + √v  S dW₁
        dv = κ(θ - v) dt + σᵥ √v dW₂
        dW₁ dW₂ = ρ dt

    Parameters
    ----------
    S        : spot price
    K        : strike
    T        : time to expiry (years)
    r        : continuously compounded risk-free rate
    q        : continuous dividend yield
    v0       : initial variance (v₀ > 0; implied vol ≈ √v₀)
    kappa    : mean-reversion speed (κ > 0)
    theta    : long-run variance (θ > 0; long-run vol ≈ √θ)
    sigma_v  : volatility of variance (σᵥ > 0)
    rho      : spot-variance correlation (-1 < ρ < 1)
    option_type : "call" or "put"

    Returns
    -------
    Option price (float).
    """
    if T <= 0:
        intrinsic = max(S - K, 0.0) if option_type == "call" else max(K - S, 0.0)
        return float(intrinsic)

    args1 = (S, K, T, r, q, v0, kappa, theta, sigma_v, rho, 1)
    args2 = (S, K, T, r, q, v0, kappa, theta, sigma_v, rho, 2)

    I1, _ = integrate.quad(
        _heston_cf_integrand, 1e-6, 500.0,
        args=args1, limit=500, epsabs=1e-7, epsrel=1e-7,
    )
    I2, _ = integrate.quad(
        _heston_cf_integrand, 1e-6, 500.0,
        args=args2, limit=500, epsabs=1e-7, epsrel=1e-7,
    )

    P1 = 0.5 + I1 / np.pi
    P2 = 0.5 + I2 / np.pi

    call = S * np.exp(-q * T) * P1 - K * np.exp(-r * T) * P2

    if option_type == "call":
        return max(float(call), 0.0)
    else:
        put = call - S * np.exp(-q * T) + K * np.exp(-r * T)
        return max(float(put), 0.0)


# ── Monte Carlo (Euler-Maruyama with full truncation) ─────────────────────────

def heston_mc_price(
    S: float,
    K: float,
    T: float,
    r: float,
    q: float,
    v0: float,
    kappa: float,
    theta: float,
    sigma_v: float,
    rho: float,
    option_type: str = "call",
    num_simulations: int = 10000,
    num_steps: int = 252,
    seed: int | None = None,
) -> float:
    """
    Monte Carlo Heston pricing using Euler-Maruyama with full truncation for variance.

    Useful as a cross-check for the semi-analytic result.
    """
    rng = np.random.default_rng(seed)
    dt = T / num_steps
    sqrt_dt = np.sqrt(dt)
    sqrt_1mr2 = np.sqrt(max(1.0 - rho ** 2, 0.0))

    Z1 = rng.standard_normal((num_steps, num_simulations))
    Z2 = rng.standard_normal((num_steps, num_simulations))
    # Correlate: W_v = rho*Z1 + sqrt(1-rho^2)*Z2
    Wv = rho * Z1 + sqrt_1mr2 * Z2

    v = np.full(num_simulations, float(v0))
    log_S = np.full(num_simulations, np.log(float(S)))

    for i in range(num_steps):
        v_pos = np.maximum(v, 0.0)          # full truncation
        sqrt_v = np.sqrt(v_pos)

        log_S += (r - q - 0.5 * v_pos) * dt + sqrt_v * sqrt_dt * Z1[i]
        v += kappa * (theta - v_pos) * dt + sigma_v * sqrt_v * sqrt_dt * Wv[i]

    S_T = np.exp(log_S)

    if option_type == "call":
        payoffs = np.maximum(S_T - K, 0.0)
    else:
        payoffs = np.maximum(K - S_T, 0.0)

    return float(np.exp(-r * T) * np.mean(payoffs))
