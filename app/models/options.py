from __future__ import annotations
from datetime import date
from typing import Literal, Optional, Union
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .common import VolatilityInput, VolatilityUsed, VolData


# ── Shared option fields mixin ────────────────────────────────────────────────

class _OptionBase(BaseModel):
    model: Literal["black_scholes", "bachelier", "cev", "monte_carlo", "heston"] = Field(
        "black_scholes",
        description=(
            "Pricing model. `heston` requires `volatility.surface_type='heston'` with "
            "parameters v0, kappa, theta, sigma_v, rho in `other_params`. "
            "Add `use_mc: true` to `other_params` to use Monte Carlo instead of semi-analytic."
        ),
    )
    option_type: Literal["call", "put"] = Field("call", description="Option right.")

    spot: float = Field(..., gt=0, description="Current underlying price (S).")
    strike: float = Field(..., gt=0, description="Option strike price (K).")

    settlement_date: date = Field(..., description="Trade date / valuation date.")
    expiry_date: date = Field(..., description="Option expiry / expiration date.")

    rate: float = Field(..., description="Continuously compounded risk-free rate (e.g. 0.05).")
    dividend_yield: float = Field(0.0, description="Continuous dividend yield.")

    day_count: Literal["ACT/365", "ACT/360", "30/360", "ACT/ACT"] = Field(
        "ACT/365", description="Day count convention for computing time to expiry."
    )

    volatility: Union[VolatilityInput, float] = Field(
        ...,
        description=(
            "Volatility input. Scalar (e.g. `0.2`) or a `VolatilityInput` object for "
            "constant or matrix (vol surface) configurations."
        ),
    )

    @field_validator("volatility", mode="before")
    @classmethod
    def _coerce_scalar_vol(cls, v):
        if isinstance(v, (int, float)):
            return VolatilityInput(surface_type="constant", data=VolData(vol=float(v)))
        return v

    @model_validator(mode="after")
    def _check_dates(self):
        if self.expiry_date <= self.settlement_date:
            raise ValueError("expiry_date must be after settlement_date")
        return self


# ── /options/price ────────────────────────────────────────────────────────────

class OptionPriceRequest(_OptionBase):
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "model": "black_scholes",
            "option_type": "call",
            "spot": 100.0,
            "strike": 105.0,
            "rate": 0.05,
            "dividend_yield": 0.0,
            "settlement_date": "2026-04-01",
            "expiry_date": "2027-04-01",
            "day_count": "ACT/365",
            "volatility": 0.2,
            "num_simulations": 10000,
            "seed": None,
            "include_insights": False,
        }
    })

    num_simulations: int = Field(10000, gt=0, description="Monte Carlo path count (model='monte_carlo' only).")
    seed: Optional[int] = Field(None, description="Random seed for reproducible Monte Carlo results.")
    include_insights: bool = Field(False, description="Return a plain-language interpretation of the result.")


class OptionPriceResponse(BaseModel):
    price: float
    time_to_expiry_days: int = Field(..., description="Calendar days from settlement to expiry.")
    model_used: str
    volatility_used: VolatilityUsed
    insights: Optional[dict] = None


# ── /options/greeks ───────────────────────────────────────────────────────────

class GreeksRequest(_OptionBase):
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "model": "black_scholes",
            "option_type": "call",
            "spot": 100.0,
            "strike": 105.0,
            "rate": 0.05,
            "dividend_yield": 0.0,
            "settlement_date": "2026-04-01",
            "expiry_date": "2027-04-01",
            "day_count": "ACT/365",
            "volatility": 0.2,
            "method": "analytic",
            "bump_size": 0.01,
            "num_simulations": 10000,
            "seed": None,
            "include_insights": False,
        }
    })

    method: Literal["analytic", "finite_difference"] = Field(
        "analytic",
        description=(
            "`analytic` uses closed-form derivatives (Black-Scholes only). "
            "`finite_difference` uses bump-and-reprice and works with all models and vol surfaces."
        ),
    )
    bump_size: float = Field(0.01, description="Relative bump size for the finite-difference method.")
    num_simulations: int = Field(10000, gt=0, description="Monte Carlo path count (model='monte_carlo' only).")
    seed: Optional[int] = Field(None, description="Random seed for reproducible Monte Carlo results.")
    include_insights: bool = Field(False, description="Return a plain-language interpretation of the Greeks.")


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


# ── /options/volatility ───────────────────────────────────────────────────────

class VolatilityRequest(BaseModel):
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "type": "implied",
            "option_price": 8.73,
            "option_type": "call",
            "spot": 100.0,
            "strike": 105.0,
            "rate": 0.05,
            "dividend_yield": 0.0,
            "settlement_date": "2026-04-01",
            "expiry_date": "2027-04-01",
            "day_count": "ACT/365",
            "vol_type": "log_normal",
            "initial_guess": 0.2,
            "tolerance": 1e-6,
            "max_iterations": 100,
        }
    })

    type: Literal["implied", "historical"] = Field(
        ...,
        description="`implied` back-solves from a market price; `historical` estimates from a price series.",
    )

    # implied fields
    option_price: Optional[float] = Field(None, description="[implied] Observed market price of the option.")
    option_type: Optional[Literal["call", "put"]] = Field(None, description="[implied] Option right.")
    spot: Optional[float] = Field(None, description="[implied] Current underlying price.")
    strike: Optional[float] = Field(None, description="[implied] Strike price.")
    rate: Optional[float] = Field(None, description="[implied] Continuously compounded risk-free rate.")
    dividend_yield: float = Field(0.0, description="[implied] Continuous dividend yield.")
    settlement_date: Optional[date] = Field(None, description="[implied] Valuation date.")
    expiry_date: Optional[date] = Field(None, description="[implied] Option expiry date.")
    day_count: Literal["ACT/365", "ACT/360", "30/360", "ACT/ACT"] = Field(
        "ACT/365", description="[implied] Day count convention for time-to-expiry."
    )
    vol_type: Literal["log_normal", "normal"] = Field(
        "log_normal",
        description="[implied] Vol model assumption: `log_normal` (Black-Scholes) or `normal` (Bachelier).",
    )
    initial_guess: float = Field(0.2, description="[implied] Starting vol for the Newton-Raphson solver.")
    tolerance: float = Field(1e-6, description="[implied] Solver convergence tolerance on price error.")
    max_iterations: int = Field(100, description="[implied] Maximum solver iterations.")

    # historical fields
    prices: Optional[list[float]] = Field(None, description="[historical] Ordered price series (minimum 2).")
    method: Literal["log_returns", "simple_returns"] = Field(
        "log_returns", description="[historical] Return type used to compute the standard deviation."
    )
    window: Optional[int] = Field(None, description="[historical] Rolling window. `null` = full series.")
    annualization_factor: int = Field(252, description="[historical] Periods per year for annualisation (252 daily, 52 weekly).")

    @model_validator(mode="after")
    def _validate_required(self):
        if self.type == "implied":
            required = ["option_price", "option_type", "spot", "strike", "rate", "settlement_date", "expiry_date"]
            missing = [f for f in required if getattr(self, f) is None]
            if missing:
                raise ValueError(f"Missing required fields for implied vol: {missing}")
            if self.expiry_date <= self.settlement_date:
                raise ValueError("expiry_date must be after settlement_date")
        else:
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
    time_to_expiry_days: Optional[int] = Field(None, description="[implied] Calendar days from settlement to expiry.")
    convergence: Optional[ConvergenceInfo] = None
    insights: Optional[dict] = None


# ── /options/strategies ───────────────────────────────────────────────────────

class StrategyLeg(BaseModel):
    type: Literal["call", "put"] = Field(..., description="Option type for this leg.")
    position: Literal["long", "short"] = Field(..., description="Long (bought) or short (sold).")
    strike: float = Field(..., gt=0, description="Strike price of this leg.")
    expiry_date: date = Field(..., description="Expiry date of this leg.")
    premium: float = Field(..., ge=0, description="Option premium paid (long) or received (short) per unit.")


class StrategyRequest(BaseModel):
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "spot": 100.0,
            "settlement_date": "2026-04-01",
            "legs": [
                {"type": "call", "position": "long",  "strike": 100.0, "expiry_date": "2027-04-01", "premium": 10.0},
                {"type": "call", "position": "short", "strike": 110.0, "expiry_date": "2027-04-01", "premium": 5.0},
            ],
        }
    })

    spot: float = Field(..., gt=0, description="Current underlying spot price.")
    settlement_date: date = Field(..., description="Trade / valuation date.")
    legs: list[StrategyLeg] = Field(..., min_length=1, description="Option legs forming the strategy.")


class PayoffPoint(BaseModel):
    spot: float
    value: float


class StrategyResponse(BaseModel):
    strategy: str = Field(..., description="Identified strategy name (e.g. 'bull_call_spread', 'straddle').")
    max_profit: Optional[float] = Field(None, description="Maximum profit. `null` if theoretically unlimited.")
    max_loss: Optional[float] = Field(None, description="Maximum loss. `null` if theoretically unlimited.")
    breakevens: list[float] = Field(..., description="Spot price(s) at which the net payoff is zero.")
    payoff: list[PayoffPoint] = Field(..., description="Sampled payoff profile across a spot price range.")
