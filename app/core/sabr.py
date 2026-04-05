import numpy as np


def sabr_implied_vol(
    F: float,
    K: float,
    T: float,
    alpha: float,
    beta: float,
    rho: float,
    nu: float,
) -> float:
    """
    Hagan et al. (2002) SABR implied Black-Scholes volatility.

    Parameters
    ----------
    F     : forward price F = S * exp((r - q) * T)
    K     : strike
    T     : time to expiry (years)
    alpha : initial vol level (alpha > 0)
    beta  : CEV exponent in [0, 1]; beta=1 → log-normal backbone
    rho   : S-v Brownian correlation (-1 < rho < 1)
    nu    : vol of vol (nu >= 0)

    Returns
    -------
    Implied Black-Scholes volatility (float).
    """
    if F <= 0 or K <= 0:
        raise ValueError("Forward and strike must be positive")
    if not (0 <= beta <= 1):
        raise ValueError("beta must be in [0, 1]")
    if alpha <= 0:
        raise ValueError("alpha must be positive")

    FK = F * K
    FK_mid = FK ** ((1.0 - beta) / 2.0)

    # ── time-correction factor (same for ATM and non-ATM) ────────────────────
    eps = 1e-12
    time_factor = 1.0 + (
        ((1.0 - beta) ** 2 / 24.0) * alpha ** 2 / (FK ** (1.0 - beta))
        + rho * beta * nu * alpha / (4.0 * FK_mid + eps)
        + (2.0 - 3.0 * rho ** 2) / 24.0 * nu ** 2
    ) * T

    # ── ATM case (|F - K| / F < 1e-6) ────────────────────────────────────────
    if abs(F - K) / max(F, 1e-12) < 1e-6:
        # F ≈ K → use ATM expansion
        atm_denom = (
            F ** (1.0 - beta)
            * (1.0 + (1.0 - beta) ** 2 / 24.0 * np.log(F / K + eps) ** 2
               + (1.0 - beta) ** 4 / 1920.0 * np.log(F / K + eps) ** 4)
        )
        return float(alpha / atm_denom * time_factor)

    log_FK = np.log(F / K)
    log_expansion = 1.0 + (1.0 - beta) ** 2 / 24.0 * log_FK ** 2 + (1.0 - beta) ** 4 / 1920.0 * log_FK ** 4

    # ── z / χ(z) term ─────────────────────────────────────────────────────────
    if nu < 1e-10:
        # no vol-of-vol → z/chi → 1
        zchi = 1.0
    else:
        z = nu / alpha * FK_mid * log_FK
        discriminant = max(1.0 - 2.0 * rho * z + z ** 2, 0.0)
        chi = np.log((np.sqrt(discriminant) + z - rho) / (1.0 - rho))
        zchi = z / chi if abs(chi) > 1e-12 else 1.0

    return float(alpha / (FK_mid * log_expansion) * zchi * time_factor)


def sabr_implied_vol_batch(
    Fs: np.ndarray,
    Ks: np.ndarray,
    Ts: np.ndarray,
    alpha: float,
    beta: float,
    rho: float,
    nu: float,
) -> np.ndarray:
    """
    Vectorized SABR implied vol for arrays of (F, K, T).

    Same Hagan et al. (2002) formula as the scalar version, but computed
    on NumPy arrays for use in calibration loss functions.
    """
    eps = 1e-12
    one_m_beta = 1.0 - beta

    FK = Fs * Ks
    FK_mid = FK ** (one_m_beta / 2.0)

    # Time-correction factor
    time_factor = 1.0 + (
        (one_m_beta ** 2 / 24.0) * alpha ** 2 / (FK ** one_m_beta + eps)
        + rho * beta * nu * alpha / (4.0 * FK_mid + eps)
        + (2.0 - 3.0 * rho ** 2) / 24.0 * nu ** 2
    ) * Ts

    log_FK = np.log(Fs / Ks + eps)
    log_expansion = (1.0
                     + (one_m_beta ** 2 / 24.0) * log_FK ** 2
                     + (one_m_beta ** 4 / 1920.0) * log_FK ** 4)

    is_atm = np.abs(Fs - Ks) / np.maximum(Fs, eps) < 1e-6

    # z / chi(z) term
    if nu < 1e-10:
        zchi = np.ones_like(Fs)
    else:
        z = nu / alpha * FK_mid * log_FK
        discriminant = np.maximum(1.0 - 2.0 * rho * z + z ** 2, 0.0)
        chi = np.log((np.sqrt(discriminant) + z - rho) / (1.0 - rho + eps))
        zchi = np.where(np.abs(chi) > 1e-12, z / chi, 1.0)

    # ATM: simplified denominator
    atm_denom = Fs ** one_m_beta * log_expansion
    atm_vol = alpha / atm_denom * time_factor

    # Non-ATM
    non_atm_vol = alpha / (FK_mid * log_expansion) * zchi * time_factor

    return np.where(is_atm, atm_vol, non_atm_vol)
