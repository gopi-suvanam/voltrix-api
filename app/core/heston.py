import numpy as np
from scipy import integrate


# ── Gauss-Legendre quadrature nodes (precomputed) ───────────────────────────
_GL_N = 128
_GL_NODES_01, _GL_WEIGHTS_01 = np.polynomial.legendre.leggauss(_GL_N)
# Map from [-1, 1] to [0, 1]
_GL_NODES_01 = 0.5 * (_GL_NODES_01 + 1.0)
_GL_WEIGHTS_01 = 0.5 * _GL_WEIGHTS_01


# ── Semi-analytic (characteristic function) ───────────────────────────────────

def _heston_cf_integrand(phi: float, S, K, T, r, q, v0, kappa, theta, sigma_v, rho, j: int) -> float:
    """
    Heston (1993) characteristic function integrand for P1 (j=1) or P2 (j=2).

    Uses the numerically stable "log" formulation that avoids separate
    computation of g and exp(d·T) which overflow for large σᵥ or T.

    P_j = 0.5 + (1/π) * ∫₀^∞  Re[ exp(-i·φ·ln K) · f_j(φ) / (i·φ) ] dφ
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
    sv2 = sigma_v ** 2

    d = np.sqrt((rho * sigma_v * i * phi - b) ** 2
                - sv2 * (2.0 * u * i * phi - phi ** 2))

    # Albrecher et al. (2007): choose branch so that Re(d) >= 0
    if d.real < 0:
        d = -d

    # Stable formulation: work with b_minus = b - rho*sv*i*phi - d (the
    # denominator of g).  Express C and D using log1p-style identities to
    # avoid computing exp(d*T) alone which overflows.
    b_plus  = b - rho * sigma_v * i * phi + d
    b_minus = b - rho * sigma_v * i * phi - d

    # g = b_plus / b_minus
    # Key identity: log((1 - g*exp(dT)) / (1 - g))
    #   = log(b_minus - b_plus*exp(dT)) - log(b_minus - b_plus) + d*T
    # We rewrite to avoid exp(d*T) overflow by factoring out exp(d*T):
    #   b_minus - b_plus*exp(dT) = exp(dT)*(b_minus*exp(-dT) - b_plus)
    # Then: log(...) = d*T + log(b_minus*exp(-dT) - b_plus) - log(b_minus - b_plus)
    # Since Re(d) >= 0, exp(-dT) is bounded.
    exp_neg_dT = np.exp(-d * T)

    # D = b_plus / sv2 * (1 - exp(dT)) / (1 - g*exp(dT))
    #   = b_plus * (1 - exp(dT)) / (b_minus - b_plus * exp(dT))
    #   = b_plus * (exp(-dT) - 1) / (b_minus * exp(-dT) - b_plus)
    denom = b_minus * exp_neg_dT - b_plus
    if abs(denom) < 1e-30:
        return 0.0
    D = b_plus / sv2 * (exp_neg_dT - 1.0) / denom

    # C = (r-q)*i*phi*T + a/sv2 * (b_plus*T - 2*log((1-g*exp(dT))/(1-g)))
    # log term = d*T + log(b_minus*exp(-dT) - b_plus) - log(b_minus - b_plus)
    log_arg1 = denom  # b_minus*exp(-dT) - b_plus
    log_arg2 = b_minus - b_plus
    if abs(log_arg1) < 1e-30 or abs(log_arg2) < 1e-30:
        return 0.0
    log_term = d * T + np.log(log_arg1) - np.log(log_arg2)

    C = (r - q) * i * phi * T + a / sv2 * (b_plus * T - 2.0 * log_term)

    f_j = np.exp(C + D * v0 + i * phi * ln_F)

    result = float(np.real(np.exp(-i * phi * np.log(K)) * f_j / (i * phi)))
    return result if np.isfinite(result) else 0.0


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

    if not np.isfinite(call):
        # Fallback: return intrinsic value when CF integration blows up
        fwd = S * np.exp((r - q) * T)
        call = max(fwd - K, 0.0) * np.exp(-r * T)

    if option_type == "call":
        return max(float(call), 0.0)
    else:
        put = call - S * np.exp(-q * T) + K * np.exp(-r * T)
        return max(float(put), 0.0) if np.isfinite(put) else max(float(K * np.exp(-r * T) - S * np.exp(-q * T)), 0.0)


# ── Vectorized batch pricer (for calibration) ───────────────────────────────

def _heston_cf_vec(phi, ln_F, T, r, q, v0, kappa, theta, sigma_v, rho, j):
    """
    Vectorized Heston characteristic function.

    phi  : (N_quad,)       quadrature nodes
    ln_F : (N_obs,)        log-forward for each observation
    T    : (N_obs,)        time to expiry
    Returns: (N_obs, N_quad) complex array of f_j(phi)
    """
    i = 1j
    if j == 1:
        u, b = 0.5, kappa - rho * sigma_v
    else:
        u, b = -0.5, kappa

    a = kappa * theta
    sv2 = sigma_v ** 2

    # phi: (Q,) -> (1, Q);  T: (N,) -> (N, 1)
    phi = phi[np.newaxis, :]       # (1, Q)
    T_  = T[:, np.newaxis]         # (N, 1)
    ln_F_ = ln_F[:, np.newaxis]    # (N, 1)

    d = np.sqrt((rho * sigma_v * i * phi - b) ** 2
                - sv2 * (2.0 * u * i * phi - phi ** 2))

    # Branch selection: Re(d) >= 0
    d = np.where(d.real < 0, -d, d)

    # Stable formulation using exp(-d*T) instead of exp(d*T) to avoid overflow
    b_plus  = b - rho * sigma_v * i * phi + d   # (1, Q)
    b_minus = b - rho * sigma_v * i * phi - d   # (1, Q)

    exp_neg_dT = np.exp(-d * T_)  # bounded since Re(d) >= 0

    # denom = b_minus * exp(-dT) - b_plus
    denom = b_minus * exp_neg_dT - b_plus  # (N, Q)

    D = b_plus / sv2 * (exp_neg_dT - 1.0) / denom

    # log term = d*T + log(b_minus*exp(-dT) - b_plus) - log(b_minus - b_plus)
    log_arg2 = b_minus - b_plus
    # Use safe log: replace tiny values to avoid log(0)
    safe_denom = np.where(np.abs(denom) < 1e-30, 1e-30 + 0j, denom)
    safe_log_arg2 = np.where(np.abs(log_arg2) < 1e-30, 1e-30 + 0j, log_arg2)
    log_term = d * T_ + np.log(safe_denom) - np.log(safe_log_arg2)

    rqT = (r - q) * T_  # (N, 1)

    C = rqT * i * phi + a / sv2 * (b_plus * T_ - 2.0 * log_term)

    result = np.exp(C + D * v0 + i * phi * ln_F_)  # (N, Q)
    # Clamp numerical blow-ups so downstream quadrature stays finite
    result = np.where(np.isfinite(result), result, 0.0 + 0.0j)
    return result


def heston_price_batch(
    S: float, Ks: np.ndarray, Ts: np.ndarray,
    r: float, q: float,
    v0: float, kappa: float, theta: float, sigma_v: float, rho: float,
    option_types: list[str],
) -> np.ndarray:
    """
    Vectorized Heston pricing for multiple (K, T, option_type) observations.

    Uses fixed Gauss-Legendre quadrature (64 points) mapped onto [0, phi_max]
    via a change of variable.  Much faster than per-observation scipy.quad.
    """
    Ks = np.asarray(Ks, dtype=np.float64)
    Ts = np.asarray(Ts, dtype=np.float64)
    N = len(Ks)

    phi_max = 200.0  # sufficient for convergence; integrand decays fast
    phi = _GL_NODES_01 * phi_max + 1e-8   # (Q,) avoid phi=0
    w   = _GL_WEIGHTS_01 * phi_max         # (Q,)

    ln_F = np.log(S) + (r - q) * Ts       # (N,)
    ln_K = np.log(Ks)                      # (N,)

    # f_j: (N, Q)
    f1 = _heston_cf_vec(phi, ln_F, Ts, r, q, v0, kappa, theta, sigma_v, rho, 1)
    f2 = _heston_cf_vec(phi, ln_F, Ts, r, q, v0, kappa, theta, sigma_v, rho, 2)

    # integrand: Re[ exp(-i*phi*ln K) * f_j / (i*phi) ]   shape (N, Q)
    i = 1j
    e_neg_iphi_lnK = np.exp(-i * phi[np.newaxis, :] * ln_K[:, np.newaxis])  # (N, Q)
    inv_iphi = 1.0 / (i * phi[np.newaxis, :])  # (1, Q)

    integrand1 = np.real(e_neg_iphi_lnK * f1 * inv_iphi)  # (N, Q)
    integrand2 = np.real(e_neg_iphi_lnK * f2 * inv_iphi)  # (N, Q)

    I1 = integrand1 @ w  # (N,)
    I2 = integrand2 @ w  # (N,)

    P1 = 0.5 + I1 / np.pi
    P2 = 0.5 + I2 / np.pi

    call = S * np.exp(-q * Ts) * P1 - Ks * np.exp(-r * Ts) * P2

    is_put = np.array([t == "put" for t in option_types])
    prices = np.where(
        is_put,
        call - S * np.exp(-q * Ts) + Ks * np.exp(-r * Ts),
        call,
    )
    prices = np.where(np.isfinite(prices), prices, 0.0)
    return np.maximum(prices, 0.0)


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
