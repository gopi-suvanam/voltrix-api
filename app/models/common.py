from typing import Any, Literal, Optional
from pydantic import BaseModel, Field, model_validator


class VolData(BaseModel):
    # Constant surface
    vol: Optional[float] = Field(None, description="Constant volatility value (e.g. `0.2` for 20%). Required when `surface_type='constant'`.")
    # Matrix surface
    strikes: Optional[list[float]] = Field(None, description="Ordered strike levels for the vol matrix. Required when `surface_type='matrix'`.")
    maturities: Optional[list[float]] = Field(None, description="Ordered maturities (in years) for the vol matrix. Required when `surface_type='matrix'`.")
    vol_matrix: Optional[list[list[float]]] = Field(
        None,
        description=(
            "2-D vol surface: `vol_matrix[i][j]` is the vol at `strikes[i]` and `maturities[j]`. "
            "Shape must be `len(strikes) × len(maturities)`."
        ),
    )


# Required keys per parametric surface type
_PARAMETRIC_REQUIRED: dict[str, list[str]] = {
    "sabr":   ["alpha", "beta", "rho", "nu"],
    "svi":    ["a", "b", "rho", "m", "sigma"],
    "heston": ["v0", "kappa", "theta", "sigma_v", "rho"],
}


class VolatilityInput(BaseModel):
    vol_type: Literal["log_normal", "normal", "cev"] = Field(
        "log_normal",
        description="Volatility convention: `log_normal` (Black-Scholes), `normal` (Bachelier), or `cev`.",
    )
    surface_type: Literal["constant", "matrix", "sabr", "svi", "heston"] = Field(
        "constant",
        description=(
            "`constant` — single scalar vol; "
            "`matrix` — bilinear-interpolated strike×maturity surface; "
            "`sabr` — Hagan SABR implied-vol formula (other_params: alpha, beta, rho, nu); "
            "`svi` — Gatheral raw SVI total-variance smile (other_params: a, b, rho, m, sigma); "
            "`heston` — Heston stochastic-vol model (other_params: v0, kappa, theta, sigma_v, rho). "
            "Use with model=`heston` for semi-analytic or MC pricing."
        ),
    )
    data: VolData = Field(
        default_factory=VolData,
        description=(
            "Volatility data payload. Required for `constant` (data.vol) and `matrix` surfaces. "
            "Not used for `sabr`, `svi`, or `heston` — supply parameters via `other_params` instead."
        ),
    )
    interpolation: Literal["bilinear"] = Field("bilinear", description="Interpolation method for matrix surfaces.")
    extrapolation: Literal["flat"] = Field("flat", description="Extrapolation rule outside the surface bounds.")
    other_params: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Model-specific parameters.\n"
            "- CEV: `cev_beta` (elasticity 0–1, default 1.0)\n"
            "- SABR: `alpha` (>0), `beta` (0–1), `rho` (−1..1), `nu` (≥0)\n"
            "- SVI: `a`, `b` (≥0), `rho` (−1..1), `m`, `sigma` (>0)\n"
            "- Heston: `v0` (>0), `kappa` (>0), `theta` (>0), `sigma_v` (>0), `rho` (−1..1)"
        ),
    )

    @model_validator(mode="after")
    def _validate_data(self):
        if self.surface_type == "constant":
            if self.data.vol is None:
                raise ValueError("'data.vol' is required when surface_type='constant'")
        elif self.surface_type == "matrix":
            missing = [
                f for f in ("strikes", "maturities", "vol_matrix")
                if getattr(self.data, f) is None
            ]
            if missing:
                raise ValueError(
                    f"Matrix surface requires: {', '.join(missing)}"
                )
            n_s = len(self.data.strikes)
            n_m = len(self.data.maturities)
            if len(self.data.vol_matrix) != n_s:
                raise ValueError(
                    f"vol_matrix must have {n_s} rows (one per strike), "
                    f"got {len(self.data.vol_matrix)}"
                )
            for i, row in enumerate(self.data.vol_matrix):
                if len(row) != n_m:
                    raise ValueError(
                        f"vol_matrix row {i} must have {n_m} columns (one per maturity), "
                        f"got {len(row)}"
                    )
        elif self.surface_type in _PARAMETRIC_REQUIRED:
            needed = _PARAMETRIC_REQUIRED[self.surface_type]
            missing = [k for k in needed if k not in self.other_params]
            if missing:
                raise ValueError(
                    f"surface_type='{self.surface_type}' requires other_params keys: {missing}"
                )
        return self


class VolatilityUsed(BaseModel):
    value: float
    source: str       # "constant" | "interpolated"
    surface_type: str  # "constant" | "matrix"


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail
