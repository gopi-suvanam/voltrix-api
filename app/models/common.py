from typing import Any, Literal, Optional
from pydantic import BaseModel, model_validator


class VolData(BaseModel):
    # Constant surface
    vol: Optional[float] = None
    # Matrix surface
    strikes: Optional[list[float]] = None
    maturities: Optional[list[float]] = None
    vol_matrix: Optional[list[list[float]]] = None


class VolatilityInput(BaseModel):
    vol_type: Literal["log_normal", "normal", "cev"] = "log_normal"
    surface_type: Literal["constant", "matrix"] = "constant"
    data: VolData
    interpolation: Literal["bilinear"] = "bilinear"
    extrapolation: Literal["flat"] = "flat"
    other_params: dict[str, Any] = {}

    @model_validator(mode="after")
    def _validate_data(self):
        if self.surface_type == "constant":
            if self.data.vol is None:
                raise ValueError("'data.vol' is required when surface_type='constant'")
        else:  # matrix
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
