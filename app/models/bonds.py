from datetime import date
from typing import Literal, Optional
from pydantic import BaseModel, Field, model_validator


class BondPriceRequest(BaseModel):
    settlement_date: date = Field(..., description="Trade settlement date.")
    maturity_date: date = Field(..., description="Bond maturity date.")

    coupon_rate: float = Field(..., ge=0, description="Annual coupon rate as a decimal (e.g. 0.05 for 5%).")
    face_value: float = Field(1000.0, gt=0, description="Par / face value of the bond.")
    frequency: Literal["annual", "semi_annual", "quarterly", "monthly"] = Field(
        "semi_annual", description="Coupon payment frequency."
    )

    ytm: float = Field(..., description="Yield-to-maturity as a decimal (e.g. 0.045 for 4.5%).")
    day_count: Literal["ACT/365", "ACT/360", "30/360", "ACT/ACT"] = Field(
        "30/360", description="Day count convention for year-fraction calculations."
    )

    @model_validator(mode="after")
    def _check_dates(self):
        if self.maturity_date <= self.settlement_date:
            raise ValueError("maturity_date must be after settlement_date")
        return self


class BondPriceResponse(BaseModel):
    price: float = Field(..., description="Dirty (full) price of the bond.")
    accrued_interest: float = Field(..., description="Accrued interest since the last coupon date.")
    clean_price: float = Field(..., description="Clean price (dirty price minus accrued interest).")


class BondYieldRequest(BaseModel):
    clean_price: float = Field(..., gt=0, description="Observed clean market price of the bond.")

    settlement_date: date = Field(..., description="Trade settlement date.")
    maturity_date: date = Field(..., description="Bond maturity date.")

    coupon_rate: float = Field(..., ge=0, description="Annual coupon rate as a decimal.")
    face_value: float = Field(1000.0, gt=0, description="Par / face value of the bond.")
    frequency: Literal["annual", "semi_annual", "quarterly", "monthly"] = Field(
        "semi_annual", description="Coupon payment frequency."
    )
    day_count: Literal["ACT/365", "ACT/360", "30/360", "ACT/ACT"] = Field(
        "30/360", description="Day count convention."
    )
    initial_guess: float = Field(0.05, description="Starting yield for the Newton-Raphson solver.")

    @model_validator(mode="after")
    def _check_dates(self):
        if self.maturity_date <= self.settlement_date:
            raise ValueError("maturity_date must be after settlement_date")
        return self


class BondYieldResponse(BaseModel):
    ytm: float = Field(..., description="Yield-to-maturity as a decimal.")
    iterations: int = Field(..., description="Number of solver iterations.")
    status: str = Field(..., description="Solver status: 'converged' or 'max_iterations_reached'.")


class BondSensitivityRequest(BaseModel):
    clean_price: float = Field(..., gt=0, description="Observed clean market price.")

    settlement_date: date = Field(..., description="Trade settlement date.")
    maturity_date: date = Field(..., description="Bond maturity date.")

    coupon_rate: float = Field(..., ge=0, description="Annual coupon rate as a decimal.")
    face_value: float = Field(1000.0, gt=0, description="Par / face value of the bond.")
    frequency: Literal["annual", "semi_annual", "quarterly", "monthly"] = Field(
        "semi_annual", description="Coupon payment frequency."
    )
    ytm: float = Field(..., description="Yield-to-maturity as a decimal.")
    day_count: Literal["ACT/365", "ACT/360", "30/360", "ACT/ACT"] = Field(
        "30/360", description="Day count convention."
    )

    @model_validator(mode="after")
    def _check_dates(self):
        if self.maturity_date <= self.settlement_date:
            raise ValueError("maturity_date must be after settlement_date")
        return self


class BondSensitivityResponse(BaseModel):
    duration: float = Field(..., description="Macaulay duration in years.")
    modified_duration: float = Field(..., description="Modified duration (price sensitivity to 1 unit yield move).")
    convexity: float = Field(..., description="Convexity (second-order price sensitivity to yield).")
