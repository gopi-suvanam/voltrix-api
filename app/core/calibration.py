"""
Volatility model calibration: SABR, SVI, Heston, CEV.

Each calibrator accepts a list of pre-processed observation dicts:
    {"strike": K, "T": T, "option_type": "call"|"put", "market_price": price}

plus the market inputs S, r, q, then minimises squared pricing/vol errors
using scipy optimizers.
"""
from __future__ import annotations

import numpy as np
from scipy.optimize import minimize, differential_evolution
from typing import Any

from .sabr import sabr_implied_vol, sabr_implied_vol_batch
from .svi import svi_implied_vol, svi_implied_vol_batch
from .heston import heston_price, heston_price_batch
from .vol_engine import implied_vol as _solve_iv


# ── Helper: back-solve to log-normal implied vols ─────────────────────────────

def _market_to_ivols(observations: list[dict], S: float, r: float, q: float) -> list[tuple]:
    """
    Convert market option prices to Black-Scholes implied vols.
    Silently skips observations that fail to converge.
    Returns list of (K, T, option_type, iv).
    """
    out = []
    for obs in observations:
        K, T, opt, price = obs["strike"], obs["T"], obs["option_type"], obs["market_price"]
        try:
            iv, _, _, status = _solve_iv(
                market_price=price, S=S, K=K, T=T, r=r, q=q,
                option_type=opt, vol_type="log_normal",
            )
            if status == "converged" and 1e-4 < iv < 10.0:
                out.append((K, T, opt, iv))
        except Exception:
            pass
    return out


# ── CEV BS-implied vol approximation (used in calibration and vol endpoint) ───

def cev_bs_approximation(F: float, K: float, T: float, sigma: float, beta: float) -> float:
    """
    Approximate Black-Scholes implied vol for a CEV model using the
    Hagan-Woodward (1999) expansion.

    Parameters
    ----------
    F     : Forward price
    K     : Strike
    T     : Time to expiry (years)
    sigma : CEV volatility level
    beta  : CEV elasticity ∈ [0, 1]

    Returns
    -------
    Black-Scholes implied volatility (approximate)
    """
    if beta < 0.0:
        beta = 0.0
    if beta > 1.0:
        beta = 1.0

    eps = np.log(F / K)
    one_minus_beta = 1.0 - beta
    FK_mid = (F * K) ** (one_minus_beta / 2)

    if abs(eps) < 1e-7:
        # ATM formula
        vol = (sigma / FK_mid) * (
            1.0
            + (
                one_minus_beta ** 2 / 24.0 * sigma ** 2 / FK_mid ** 2
                + one_minus_beta ** 2 / 24.0
            )
            * T
        )
    else:
        # Off-ATM: include expansion denominator
        denom = 1.0 + (one_minus_beta ** 2 / 24.0) * eps ** 2 + (one_minus_beta ** 4 / 1920.0) * eps ** 4
        vol = sigma / (FK_mid * denom) * (
            1.0
            + (
                one_minus_beta ** 2 / 24.0 * sigma ** 2 / FK_mid ** 2
                + one_minus_beta ** 2 / 24.0
            )
            * T
        )

    return max(float(vol), 1e-6)


def _cev_bs_approx_batch(
    Fs: np.ndarray, Ks: np.ndarray, Ts: np.ndarray,
    sigma: float, beta: float,
) -> np.ndarray:
    """Vectorized Hagan-Woodward CEV→BS implied vol approximation."""
    beta = float(np.clip(beta, 0.0, 1.0))
    one_m_beta = 1.0 - beta
    eps_arr = np.log(Fs / Ks)
    FK_mid = (Fs * Ks) ** (one_m_beta / 2.0)

    time_corr = 1.0 + (
        one_m_beta ** 2 / 24.0 * sigma ** 2 / (FK_mid ** 2 + 1e-30)
        + one_m_beta ** 2 / 24.0
    ) * Ts

    is_atm = np.abs(eps_arr) < 1e-7

    # ATM
    atm_vol = (sigma / FK_mid) * time_corr

    # Non-ATM
    denom = (1.0
             + (one_m_beta ** 2 / 24.0) * eps_arr ** 2
             + (one_m_beta ** 4 / 1920.0) * eps_arr ** 4)
    non_atm_vol = sigma / (FK_mid * denom) * time_corr

    return np.maximum(np.where(is_atm, atm_vol, non_atm_vol), 1e-6)


# ── SABR calibration ──────────────────────────────────────────────────────────

def calibrate_sabr(
    observations: list[dict],
    S: float,
    r: float,
    q: float,
    beta: float = 0.5,
) -> dict[str, Any]:
    """
    Calibrate SABR (alpha, rho, nu) to market implied vols with beta fixed.

    Minimises sum of squared (model_iv − market_iv)² across all observations.
    Uses L-BFGS-B with multiple restarts.
    """
    ivols = _market_to_ivols(observations, S, r, q)
    if len(ivols) < 3:
        raise ValueError(
            f"SABR calibration requires at least 3 valid market observations "
            f"(got {len(ivols)} after implied-vol extraction)"
        )

    beta = float(np.clip(beta, 0.0, 1.0))

    # Pre-extract arrays for vectorized loss
    Ks_arr = np.array([x[0] for x in ivols])
    Ts_arr = np.array([x[1] for x in ivols])
    iv_mkts = np.array([x[3] for x in ivols])
    Fs_arr = S * np.exp((r - q) * Ts_arr)

    def loss(params: np.ndarray) -> float:
        alpha, rho, nu = params
        if alpha <= 0 or nu < 0 or abs(rho) >= 1:
            return 1e10
        try:
            iv_model = sabr_implied_vol_batch(Fs_arr, Ks_arr, Ts_arr, alpha, beta, rho, nu)
            return float(np.sum((iv_model - iv_mkts) ** 2))
        except Exception:
            return 1e10

    bounds = [(1e-4, 5.0), (-0.999, 0.999), (1e-4, 5.0)]
    starts = [[0.3, -0.3, 0.4], [0.5, 0.0, 0.6], [0.1, -0.6, 0.2], [0.4, 0.2, 0.5]]
    best = None
    for x0 in starts:
        res = minimize(loss, x0, method="L-BFGS-B", bounds=bounds, options={"maxiter": 2000})
        if best is None or res.fun < best.fun:
            best = res

    alpha, rho, nu = best.x
    iv_final = sabr_implied_vol_batch(Fs_arr, Ks_arr, Ts_arr, alpha, beta, rho, nu)
    sq_errors = (iv_final - iv_mkts) ** 2

    return {
        "alpha": float(alpha),
        "beta": float(beta),
        "rho": float(rho),
        "nu": float(nu),
        "rmse": float(np.sqrt(np.mean(sq_errors))),
        "n_observations": len(ivols),
        "converged": bool(best.success),
        "message": str(best.message),
    }


# ── SVI calibration ───────────────────────────────────────────────────────────

def calibrate_svi(
    observations: list[dict],
    S: float,
    r: float,
    q: float,
) -> dict[str, Any]:
    """
    Calibrate Gatheral raw SVI (a, b, rho, m, sigma) to market implied vols.

    Butterfly-arbitrage-free constraint: a + b·sigma·√(1-rho²) ≥ 0.
    """
    ivols = _market_to_ivols(observations, S, r, q)
    if len(ivols) < 4:
        raise ValueError(
            f"SVI calibration requires at least 4 valid market observations "
            f"(got {len(ivols)} after implied-vol extraction)"
        )

    # Pre-extract arrays for vectorized loss
    Ks_arr = np.array([x[0] for x in ivols])
    Ts_arr = np.array([x[1] for x in ivols])
    iv_mkts = np.array([x[3] for x in ivols])
    Fs_arr = S * np.exp((r - q) * Ts_arr)

    def loss(params: np.ndarray) -> float:
        a, b, rho, m, sigma = params
        if b < 0 or sigma <= 0 or abs(rho) >= 1:
            return 1e10
        if a + b * sigma * np.sqrt(1.0 - rho ** 2) < 0:
            return 1e10
        try:
            iv_model = svi_implied_vol_batch(Fs_arr, Ks_arr, Ts_arr, a, b, rho, m, sigma)
            return float(np.sum((iv_model - iv_mkts) ** 2))
        except Exception:
            return 1e10

    bounds = [(0.0, 2.0), (0.0, 2.0), (-0.999, 0.999), (-3.0, 3.0), (1e-4, 2.0)]
    x0 = [0.01, 0.1, -0.3, 0.0, 0.1]
    res = minimize(loss, x0, method="L-BFGS-B", bounds=bounds, options={"maxiter": 3000})

    a, b, rho, m, sigma = res.x
    iv_final = svi_implied_vol_batch(Fs_arr, Ks_arr, Ts_arr, a, b, rho, m, sigma)
    sq_errors = (iv_final - iv_mkts) ** 2

    return {
        "a": float(a),
        "b": float(b),
        "rho": float(rho),
        "m": float(m),
        "sigma": float(sigma),
        "rmse": float(np.sqrt(np.mean(sq_errors))),
        "n_observations": len(ivols),
        "converged": bool(res.success),
        "message": str(res.message),
    }


# ── Heston calibration ────────────────────────────────────────────────────────

def calibrate_heston(
    observations: list[dict],
    S: float,
    r: float,
    q: float,
) -> dict[str, Any]:
    """
    Calibrate Heston (v0, kappa, theta, sigma_v, rho) directly to option prices.

    Uses differential-evolution for global search followed by L-BFGS-B refinement.
    """
    if len(observations) < 5:
        raise ValueError("Heston calibration requires at least 5 option price observations")

    # Pre-extract arrays once for vectorized pricing
    Ks = np.array([o["strike"] for o in observations])
    Ts = np.array([o["T"] for o in observations])
    opt_types = [o["option_type"] for o in observations]
    p_mkts = np.array([o["market_price"] for o in observations])

    def loss(params: np.ndarray) -> float:
        v0, kappa, theta, sigma_v, rho = params
        if v0 <= 0 or kappa <= 0 or theta <= 0 or sigma_v <= 0 or abs(rho) >= 1:
            return 1e10
        try:
            prices = heston_price_batch(S, Ks, Ts, r, q, v0, kappa, theta, sigma_v, rho, opt_types)
            val = float(np.sum((prices - p_mkts) ** 2))
            return val if np.isfinite(val) else 1e10
        except Exception:
            return 1e10

    bounds = [(1e-4, 2.0), (0.01, 20.0), (1e-4, 2.0), (0.01, 3.0), (-0.999, 0.999)]

    # polish=True already runs L-BFGS-B after DE, no need for a second pass
    best = differential_evolution(
        loss, bounds, maxiter=300, seed=42, tol=1e-6, polish=True, workers=1
    )

    v0, kappa, theta, sigma_v, rho = best.x
    final_prices = heston_price_batch(S, Ks, Ts, r, q, v0, kappa, theta, sigma_v, rho, opt_types)
    sq_errors = (final_prices - p_mkts) ** 2
    rmse = float(np.sqrt(np.mean(sq_errors)))

    # Sanitize: replace any NaN/Inf with 0.0 so the result is JSON-serializable
    def _safe(x: float) -> float:
        return 0.0 if not np.isfinite(x) else x

    return {
        "v0": _safe(float(v0)),
        "kappa": _safe(float(kappa)),
        "theta": _safe(float(theta)),
        "sigma_v": _safe(float(sigma_v)),
        "rho": _safe(float(rho)),
        "rmse": _safe(rmse),
        "n_observations": len(observations),
        "converged": bool(best.success),
        "feller_condition_satisfied": bool(2.0 * kappa * theta > sigma_v ** 2),
        "message": str(best.message),
    }


# ── CEV calibration ───────────────────────────────────────────────────────────

def calibrate_cev(
    observations: list[dict],
    S: float,
    r: float,
    q: float,
) -> dict[str, Any]:
    """
    Calibrate CEV (sigma, beta) using the Hagan-Woodward implied-vol approximation.

    Avoids Monte Carlo by working analytically in implied-vol space.
    """
    ivols = _market_to_ivols(observations, S, r, q)
    if len(ivols) < 2:
        raise ValueError(
            f"CEV calibration requires at least 2 valid market observations "
            f"(got {len(ivols)} after implied-vol extraction)"
        )

    # Pre-extract arrays for vectorized loss
    Ks_arr = np.array([x[0] for x in ivols])
    Ts_arr = np.array([x[1] for x in ivols])
    iv_mkts = np.array([x[3] for x in ivols])
    Fs_arr = S * np.exp((r - q) * Ts_arr)

    def loss(params: np.ndarray) -> float:
        sigma, beta = params
        if sigma <= 0 or beta < 0 or beta > 1:
            return 1e10
        try:
            iv_model = _cev_bs_approx_batch(Fs_arr, Ks_arr, Ts_arr, sigma, beta)
            return float(np.sum((iv_model - iv_mkts) ** 2))
        except Exception:
            return 1e10

    bounds = [(1e-4, 10.0), (0.0, 1.0)]
    starts = [[0.3, 0.5], [0.2, 0.8], [0.5, 0.3], [0.15, 0.6]]
    best = None
    for x0 in starts:
        res = minimize(loss, x0, method="L-BFGS-B", bounds=bounds, options={"maxiter": 1000})
        if best is None or res.fun < best.fun:
            best = res

    sigma, beta = best.x
    iv_final = _cev_bs_approx_batch(Fs_arr, Ks_arr, Ts_arr, sigma, beta)
    sq_errors = (iv_final - iv_mkts) ** 2

    return {
        "sigma": float(sigma),
        "beta": float(beta),
        "rmse": float(np.sqrt(np.mean(sq_errors))),
        "n_observations": len(ivols),
        "converged": bool(best.success),
        "message": str(best.message),
    }
