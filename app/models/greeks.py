from typing import Literal, Optional, Union
from pydantic import BaseModel, field_validator
from .common import VolatilityInput, VolatilityUsed, VolData


class GreeksRequest(BaseModel):
    model: Literal["black_scholes", "bachelier", "cev", "monte_carlo"] = "black_scholes"
    option_type: Literal["call", "put"] = "call"

    spot: float
    strike: float
    rate: float
    time_to_maturity: float
    dividend_yield: float = 0.0

    volatility: Union[VolatilityInput, float]

    method: Literal["analytic", "finite_difference"] = "analytic"
    bump_size: float = 0.01

    num_simulations: int = 10000
    seed: Optional[int] = None
    include_insights: bool = False

    @field_validator("volatility", mode="before")
    @classmethod
    def _coerce_scalar_vol(cls, v):
        if isinstance(v, (int, float)):
            return VolatilityInput(
                surface_type="constant",
                data=VolData(vol=float(v)),
            )
        return v


class GreeksUnits(BaseModel):
    vega: str = "per 1% vol change"
    theta: str = "per day decay"


class GreeksResponse(BaseModel):
    delta: float
    gamma: float
    vega: float
    theta: float
    rho: float

    units: GreeksUnits = GreeksUnits()
    volatility_used: VolatilityUsed
    interpretation: Optional[dict] = None
