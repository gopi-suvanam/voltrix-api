from __future__ import annotations

from datetime import date
from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator


# ── Shared observation type ───────────────────────────────────────────────────

class OptionObservation(BaseModel):
    option_type: Literal["call", "put"] = Field(..., description="Option right.")
    strike: float = Field(..., gt=0, description="Strike price (K).")
    expiry_date: date = Field(..., description="Option expiry date.")
    market_price: float = Field(..., gt=0, description="Observed market price of the option.")


# ── Shared calibration request base ──────────────────────────────────────────

class CalibrationRequest(BaseModel):
    observations: list[OptionObservation] = Field(
        ...,
        min_length=1,
        description="List of market option observations used for calibration.",
    )
    spot: float = Field(..., gt=0, description="Current underlying spot price (S).")
    rate: float = Field(..., description="Continuously compounded risk-free rate (e.g. 0.05).")
    dividend_yield: float = Field(0.0, description="Continuous dividend yield.")
    settlement_date: date = Field(..., description="Valuation / trade date.")
    day_count: Literal["ACT/365", "ACT/360", "30/360", "ACT/ACT"] = Field(
        "ACT/365", description="Day count convention for computing time to expiry."
    )

    @model_validator(mode="after")
    def _check_expiries(self):
        for i, obs in enumerate(self.observations):
            if obs.expiry_date <= self.settlement_date:
                raise ValueError(
                    f"observations[{i}].expiry_date must be after settlement_date"
                )
        return self


# ── SABR ──────────────────────────────────────────────────────────────────────

class SABRCalibrationRequest(CalibrationRequest):
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "spot": 100.0,
            "rate": 0.05,
            "dividend_yield": 0.0,
            "settlement_date": "2026-04-01",
            "day_count": "ACT/365",
            "beta": 0.5,
            "observations": [
                {"option_type": "call", "strike": 90.0,  "expiry_date": "2027-04-01", "market_price": 12.5},
                {"option_type": "call", "strike": 95.0,  "expiry_date": "2027-04-01", "market_price": 9.2},
                {"option_type": "call", "strike": 100.0, "expiry_date": "2027-04-01", "market_price": 6.5},
                {"option_type": "call", "strike": 105.0, "expiry_date": "2027-04-01", "market_price": 4.3},
                {"option_type": "call", "strike": 110.0, "expiry_date": "2027-04-01", "market_price": 2.7},
            ],
        }
    })

    beta: float = Field(
        0.5, ge=0.0, le=1.0,
        description=(
            "CEV elasticity exponent (fixed during calibration). "
            "β=0 → normal model, β=0.5 → square-root, β=1 → log-normal (Black-Scholes). "
            "Commonly fixed at 0.5 or 1.0."
        ),
    )


class SABRCalibrationResponse(BaseModel):
    alpha: float = Field(..., description="Calibrated initial vol level α (> 0).")
    beta: float = Field(..., description="CEV exponent β (fixed, echoed back).")
    rho: float = Field(..., description="Calibrated spot-vol correlation ρ ∈ (−1, 1).")
    nu: float = Field(..., description="Calibrated vol-of-vol ν (≥ 0).")
    rmse: Optional[float] = Field(None, description="Root-mean-square error (implied vol units).")
    n_observations: int = Field(..., description="Number of observations used in calibration.")
    converged: bool = Field(..., description="Whether the optimizer reported convergence.")
    message: str = Field(..., description="Optimizer status message.")


# ── SVI ───────────────────────────────────────────────────────────────────────

class SVICalibrationRequest(CalibrationRequest):
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "spot": 100.0,
            "rate": 0.05,
            "dividend_yield": 0.0,
            "settlement_date": "2026-04-01",
            "day_count": "ACT/365",
            "observations": [
                {"option_type": "call", "strike": 85.0,  "expiry_date": "2027-04-01", "market_price": 16.0},
                {"option_type": "call", "strike": 90.0,  "expiry_date": "2027-04-01", "market_price": 12.5},
                {"option_type": "call", "strike": 95.0,  "expiry_date": "2027-04-01", "market_price": 9.2},
                {"option_type": "call", "strike": 100.0, "expiry_date": "2027-04-01", "market_price": 6.5},
                {"option_type": "call", "strike": 105.0, "expiry_date": "2027-04-01", "market_price": 4.3},
                {"option_type": "call", "strike": 110.0, "expiry_date": "2027-04-01", "market_price": 2.7},
            ],
        }
    })


class SVICalibrationResponse(BaseModel):
    a: float = Field(..., description="Calibrated vertical shift / total-variance level.")
    b: float = Field(..., description="Calibrated angle / breadth parameter (≥ 0).")
    rho: float = Field(..., description="Calibrated asymmetry / skew parameter ∈ (−1, 1).")
    m: float = Field(..., description="Calibrated ATM shift in log-moneyness.")
    sigma: float = Field(..., description="Calibrated curvature / width parameter (> 0).")
    rmse: Optional[float] = Field(None, description="Root-mean-square error (implied vol units).")
    n_observations: int = Field(..., description="Number of observations used in calibration.")
    converged: bool = Field(..., description="Whether the optimizer reported convergence.")
    message: str = Field(..., description="Optimizer status message.")


# ── Heston ────────────────────────────────────────────────────────────────────

class HestonCalibrationRequest(CalibrationRequest):
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "spot": 100.0,
            "rate": 0.05,
            "dividend_yield": 0.0,
            "settlement_date": "2026-04-01",
            "day_count": "ACT/365",
            "observations": [
                {"option_type": "call", "strike": 90.0,  "expiry_date": "2027-01-01", "market_price": 13.0},
                {"option_type": "call", "strike": 95.0,  "expiry_date": "2027-01-01", "market_price": 9.8},
                {"option_type": "call", "strike": 100.0, "expiry_date": "2027-01-01", "market_price": 7.0},
                {"option_type": "call", "strike": 105.0, "expiry_date": "2027-01-01", "market_price": 4.8},
                {"option_type": "call", "strike": 110.0, "expiry_date": "2027-01-01", "market_price": 3.1},
                {"option_type": "put",  "strike": 95.0,  "expiry_date": "2027-04-01", "market_price": 5.5},
                {"option_type": "put",  "strike": 100.0, "expiry_date": "2027-04-01", "market_price": 7.2},
            ],
        }
    })


class HestonCalibrationResponse(BaseModel):
    v0: float = Field(..., description="Calibrated initial variance v₀ (> 0; implied vol ≈ √v₀).")
    kappa: float = Field(..., description="Calibrated mean-reversion speed κ (> 0).")
    theta: float = Field(..., description="Calibrated long-run variance θ (> 0).")
    sigma_v: float = Field(..., description="Calibrated volatility of variance σᵥ (> 0).")
    rho: float = Field(..., description="Calibrated spot-variance correlation ρ ∈ (−1, 1).")
    rmse: Optional[float] = Field(None, description="Root-mean-square error (price units).")
    n_observations: int = Field(..., description="Number of observations used in calibration.")
    converged: bool = Field(..., description="Whether the optimizer reported convergence.")
    feller_condition_satisfied: bool = Field(
        ..., description="True when 2κθ > σᵥ² (variance stays positive almost surely)."
    )
    message: str = Field(..., description="Optimizer status message.")


# ── CEV ───────────────────────────────────────────────────────────────────────

class CEVCalibrationRequest(CalibrationRequest):
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "spot": 100.0,
            "rate": 0.05,
            "dividend_yield": 0.0,
            "settlement_date": "2026-04-01",
            "day_count": "ACT/365",
            "observations": [
                {"option_type": "call", "strike": 90.0,  "expiry_date": "2027-04-01", "market_price": 12.5},
                {"option_type": "call", "strike": 95.0,  "expiry_date": "2027-04-01", "market_price": 9.2},
                {"option_type": "call", "strike": 100.0, "expiry_date": "2027-04-01", "market_price": 6.5},
                {"option_type": "call", "strike": 105.0, "expiry_date": "2027-04-01", "market_price": 4.3},
                {"option_type": "call", "strike": 110.0, "expiry_date": "2027-04-01", "market_price": 2.7},
            ],
        }
    })


class CEVCalibrationResponse(BaseModel):
    sigma: float = Field(..., description="Calibrated CEV volatility level σ (> 0).")
    beta: float = Field(..., description="Calibrated CEV elasticity β ∈ [0, 1].")
    rmse: Optional[float] = Field(None, description="Root-mean-square error (implied vol units).")
    n_observations: int = Field(..., description="Number of observations used in calibration.")
    converged: bool = Field(..., description="Whether the optimizer reported convergence.")
    message: str = Field(..., description="Optimizer status message.")
