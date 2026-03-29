from typing import Literal, Optional
from pydantic import BaseModel, model_validator


class VolatilityRequest(BaseModel):
    type: Literal["implied", "historical"]

    # ── Implied vol fields ────────────────────────────────────────────────
    option_price: Optional[float] = None
    option_type: Optional[Literal["call", "put"]] = None
    spot: Optional[float] = None
    strike: Optional[float] = None
    rate: Optional[float] = None
    time_to_maturity: Optional[float] = None
    dividend_yield: float = 0.0
    vol_type: Literal["log_normal", "normal"] = "log_normal"
    initial_guess: float = 0.2
    tolerance: float = 1e-6
    max_iterations: int = 100

    # ── Historical vol fields ─────────────────────────────────────────────
    prices: Optional[list[float]] = None
    method: Literal["log_returns", "simple_returns"] = "log_returns"
    window: Optional[int] = None
    annualization_factor: int = 252

    @model_validator(mode="after")
    def _validate_required(self):
        if self.type == "implied":
            required = ["option_price", "option_type", "spot", "strike", "rate", "time_to_maturity"]
            missing = [f for f in required if getattr(self, f) is None]
            if missing:
                raise ValueError(f"Missing required fields for implied vol: {missing}")
        else:  # historical
            if not self.prices:
                raise ValueError("'prices' is required for historical volatility")
            if len(self.prices) < 2:
                raise ValueError("'prices' must contain at least 2 values")
        return self


class ConvergenceInfo(BaseModel):
    iterations: int
    error: float
    status: str


class VolatilityResponse(BaseModel):
    volatility: float
    type: str
    convergence: Optional[ConvergenceInfo] = None
    insights: Optional[dict] = None
