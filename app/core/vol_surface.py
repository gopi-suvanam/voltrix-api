import numpy as np
from scipy.interpolate import RegularGridInterpolator

from .sabr import sabr_implied_vol
from .svi import svi_implied_vol


def resolve_vol(
    vol_input: dict,
    K: float,
    T: float,
    S: float = 100.0,
    r: float = 0.0,
    q: float = 0.0,
) -> tuple[float, str, str]:
    """
    Resolve effective volatility from a volatility input dict.

    For parametric surfaces (sabr, svi) the forward F = S·exp((r-q)·T) is
    required to compute log-moneyness; pass S, r, q accordingly.

    For `heston` surface_type, returns sqrt(v0) as a reference volatility —
    the actual pricing is handled by heston_price() in pricing.py.

    Returns
    -------
    (sigma, source, surface_type)
        source : "constant" | "interpolated" | "sabr" | "svi" | "heston"
    """
    surface_type = vol_input.get("surface_type", "constant")
    data = vol_input.get("data", {})
    other = vol_input.get("other_params", {})

    # ── constant ──────────────────────────────────────────────────────────────
    if surface_type == "constant":
        sigma = float(data.get("vol", 0.2))
        return sigma, "constant", "constant"

    # ── matrix ────────────────────────────────────────────────────────────────
    elif surface_type == "matrix":
        strikes = np.array(data["strikes"], dtype=np.float64)
        maturities = np.array(data["maturities"], dtype=np.float64)
        vol_matrix = np.array(data["vol_matrix"], dtype=np.float64)

        s_idx = np.argsort(strikes)
        m_idx = np.argsort(maturities)
        strikes = strikes[s_idx]
        maturities = maturities[m_idx]
        vol_matrix = vol_matrix[np.ix_(s_idx, m_idx)]

        extrapolation = vol_input.get("extrapolation", "flat")
        if extrapolation == "flat":
            K_q = float(np.clip(K, strikes[0], strikes[-1]))
            T_q = float(np.clip(T, maturities[0], maturities[-1]))
        else:
            K_q, T_q = K, T

        interp = RegularGridInterpolator(
            (strikes, maturities),
            vol_matrix,
            method="linear",
            bounds_error=False,
            fill_value=None,
        )
        sigma = float(interp([[K_q, T_q]])[0])
        return sigma, "interpolated", "matrix"

    # ── SABR ──────────────────────────────────────────────────────────────────
    elif surface_type == "sabr":
        F = S * np.exp((r - q) * T)
        sigma = sabr_implied_vol(
            F=F, K=K, T=T,
            alpha=float(other["alpha"]),
            beta=float(other["beta"]),
            rho=float(other["rho"]),
            nu=float(other["nu"]),
        )
        return sigma, "sabr", "sabr"

    # ── SVI ───────────────────────────────────────────────────────────────────
    elif surface_type == "svi":
        F = S * np.exp((r - q) * T)
        sigma = svi_implied_vol(
            F=F, K=K, T=T,
            a=float(other["a"]),
            b=float(other["b"]),
            rho=float(other["rho"]),
            m=float(other["m"]),
            sigma=float(other["sigma"]),
        )
        return sigma, "svi", "svi"

    # ── Heston (reference vol only; pricing handled separately) ───────────────
    elif surface_type == "heston":
        # Return sqrt(v0) as a reference implied vol level
        v0 = float(other.get("v0", 0.04))
        sigma = float(np.sqrt(v0))
        return sigma, "heston", "heston"

    raise ValueError(f"Unknown surface_type: {surface_type}")
