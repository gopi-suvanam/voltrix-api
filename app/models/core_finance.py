import datetime
from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator


class Cashflow(BaseModel):
    date: datetime.date = Field(..., description="Payment date of this cashflow.")
    amount: float = Field(..., description="Cashflow amount (positive = inflow, negative = outflow).")


class NpvRequest(BaseModel):
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "settlement_date": "2026-04-01",
            "cashflows": [
                {"date": "2026-10-01", "amount": 500.0},
                {"date": "2027-04-01", "amount": 500.0},
                {"date": "2027-10-01", "amount": 10500.0},
            ],
            "discount_rate": 0.05,
            "day_count": "ACT/365",
        }
    })

    settlement_date: datetime.date = Field(..., description="Valuation / discount-origin date.")

    cashflows: list[Cashflow] = Field(
        ...,
        min_length=1,
        description="List of dated cashflows to discount back to settlement_date.",
    )

    discount_rate: float = Field(
        ...,
        description="Annual discount rate as a decimal (e.g. 0.05 for 5%).",
    )
    day_count: Literal["ACT/365", "ACT/360", "30/360", "ACT/ACT"] = Field(
        "ACT/365",
        description="Day count convention used to compute year fractions.",
    )

    @model_validator(mode="after")
    def _check_cashflows(self):
        for cf in self.cashflows:
            if cf.date <= self.settlement_date:
                raise ValueError(
                    f"All cashflow dates must be after settlement_date. "
                    f"Got {cf.date} which is on or before {self.settlement_date}."
                )
        return self


class NpvDetail(BaseModel):
    discount_factors: list[float]
    year_fractions: list[float]


class NpvResponse(BaseModel):
    npv: float = Field(..., description="Net present value of all cashflows.")
    details: NpvDetail = Field(..., description="Per-cashflow discount factors and year fractions.")


class PmtRequest(BaseModel):
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "principal": 100000.0,
            "rate": 0.08,
            "start_date": "2026-04-01",
            "end_date": "2031-04-01",
            "frequency": "monthly",
        }
    })

    principal: float = Field(..., gt=0, description="Loan principal amount.")
    rate: float = Field(..., ge=0, description="Annual interest rate as a decimal (e.g. 0.08 for 8%).")

    start_date: datetime.date = Field(..., description="Loan start / first payment calculation date.")
    end_date: datetime.date = Field(..., description="Loan end / final payment date.")

    frequency: Literal["weekly", "monthly", "quarterly", "semi_annual", "annual"] = Field(
        "monthly",
        description="Payment frequency.",
    )

    @model_validator(mode="after")
    def _check_dates(self):
        if self.end_date <= self.start_date:
            raise ValueError("end_date must be after start_date")
        return self


class PmtResponse(BaseModel):
    payment: float = Field(..., description="Fixed periodic payment amount.")
    num_periods: int = Field(..., description="Total number of payment periods derived from the dates.")
    total_payment: float = Field(..., description="Sum of all payments over the loan term.")
    interest_paid: float = Field(..., description="Total interest paid (total_payment - principal).")
