from fastapi import APIRouter

from ..models.bonds import (
    BondPriceRequest, BondPriceResponse,
    BondYieldRequest, BondYieldResponse,
    BondSensitivityRequest, BondSensitivityResponse,
)
from ..core.bond_math import bond_price, solve_yield, duration_convexity, accrued_interest, _dirty_price

router = APIRouter(prefix="/bonds", tags=["Bonds"])


@router.post(
    "/price",
    response_model=BondPriceResponse,
    summary="Price a bond",
    description=(
        "Compute the dirty price, accrued interest, and clean price of a fixed-coupon bond "
        "given a yield-to-maturity.\n\n"
        "Coupon payment dates are generated backwards from `maturity_date` by the coupon `frequency`. "
        "Accrued interest is calculated from the most recent coupon date to `settlement_date`.\n\n"
        "**Day count conventions:** `ACT/365`, `ACT/360`, `30/360`, `ACT/ACT`"
    ),
)
def compute_bond_price(req: BondPriceRequest):
    result = bond_price(
        settlement=req.settlement_date,
        maturity=req.maturity_date,
        coupon_rate=req.coupon_rate,
        face_value=req.face_value,
        freq=req.frequency,
        ytm=req.ytm,
        day_count=req.day_count,
    )
    return BondPriceResponse(**result)


@router.post(
    "/yield",
    response_model=BondYieldResponse,
    summary="Solve for yield-to-maturity",
    description=(
        "Back-solve for the yield-to-maturity (YTM) that equates the bond's theoretical "
        "dirty price to the observed clean price plus accrued interest.\n\n"
        "Uses Newton-Raphson iteration with numerical derivatives. "
        "The `status` field indicates whether the solver converged within `max_iterations`."
    ),
)
def compute_bond_yield(req: BondYieldRequest):
    ytm, iterations, status = solve_yield(
        clean_price=req.clean_price,
        settlement=req.settlement_date,
        maturity=req.maturity_date,
        coupon_rate=req.coupon_rate,
        face_value=req.face_value,
        freq=req.frequency,
        day_count=req.day_count,
        initial_guess=req.initial_guess,
    )
    return BondYieldResponse(
        ytm=round(ytm, 8),
        iterations=iterations,
        status=status,
    )


@router.post(
    "/sensitivity",
    response_model=BondSensitivityResponse,
    summary="Compute bond duration and convexity",
    description=(
        "Compute interest-rate sensitivities for a fixed-coupon bond.\n\n"
        "| Metric | Description |\n"
        "|--------|-------------|\n"
        "| **duration** | Macaulay duration — weighted-average time to cashflow receipt (years) |\n"
        "| **modified_duration** | Price change per 1-unit (100 bp) yield move |\n"
        "| **convexity** | Second-order price sensitivity; improves duration estimate for large yield moves |\n\n"
        "Provide `clean_price` and `ytm`; accrued interest is computed internally."
    ),
)
def compute_bond_sensitivity(req: BondSensitivityRequest):
    ai = accrued_interest(
        settlement=req.settlement_date,
        maturity=req.maturity_date,
        coupon_rate=req.coupon_rate,
        face_value=req.face_value,
        freq=req.frequency,
        day_count=req.day_count,
    )
    dirty = req.clean_price + ai

    result = duration_convexity(
        settlement=req.settlement_date,
        maturity=req.maturity_date,
        coupon_rate=req.coupon_rate,
        face_value=req.face_value,
        freq=req.frequency,
        ytm=req.ytm,
        dirty_price=dirty,
        day_count=req.day_count,
    )
    return BondSensitivityResponse(**result)
