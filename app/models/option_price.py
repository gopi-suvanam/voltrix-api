from typing import Literal, Optional, Union
from pydantic import BaseModel, field_validator
from .common import VolatilityInput, VolatilityUsed, VolData


class OptionPriceRequest(BaseModel):
    model: Literal["black_scholes", "bachelier", "cev", "monte_carlo"] = "black_scholes"
    option_type: Literal["call", "put"] = "call"

    spot: float
    strike: float
    rate: float
    time_to_maturity: float
    dividend_yield: float = 0.0

    volatility: Union[VolatilityInput, float]

    num_simulations: int = 10000
    seed: Optional[int] = None
    include_insights: bool = False

    @field_validator("volatility", mode="before")
    @classmethod
    def _coerce_scalar_vol(cls, v):
        """Auto-convert a bare float/int to a constant VolatilityInput."""
        if isinstance(v, (int, float)):
            return VolatilityInput(
                surface_type="constant",
                data=VolData(vol=float(v)),
            )
        return v

    @field_validator("spot", "strike")
    @classmethod
    def _must_be_positive(cls, v, info):
        if v <= 0:
            raise ValueError(f"'{info.field_name}' must be > 0")
        return v

    @field_validator("time_to_maturity")
    @classmethod
    def _non_negative_maturity(cls, v):
        if v < 0:
            raise ValueError("time_to_maturity must be >= 0")
        return v


class OptionPriceInputs(BaseModel):
    spot: float
    strike: float
    time_to_maturity: float


class OptionPriceResponse(BaseModel):
    price: float
    model_used: str
    volatility_used: VolatilityUsed
    inputs: OptionPriceInputs
    insights: Optional[dict] = None
