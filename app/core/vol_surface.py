import numpy as np
from scipy.interpolate import RegularGridInterpolator


def resolve_vol(vol_input: dict, K: float, T: float) -> tuple[float, str, str]:
    """
    Resolve effective volatility from a volatility input dict.

    Returns:
        (sigma, source, surface_type)
        source: "constant" | "interpolated"
    """
    surface_type = vol_input.get("surface_type", "constant")
    data = vol_input.get("data", {})

    if surface_type == "constant":
        sigma = float(data.get("vol", 0.2))
        return sigma, "constant", "constant"

    elif surface_type == "matrix":
        strikes = np.array(data["strikes"], dtype=np.float64)
        maturities = np.array(data["maturities"], dtype=np.float64)
        vol_matrix = np.array(data["vol_matrix"], dtype=np.float64)

        # Ensure strictly increasing axes (sort if needed)
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

    raise ValueError(f"Unknown surface_type: {surface_type}")
