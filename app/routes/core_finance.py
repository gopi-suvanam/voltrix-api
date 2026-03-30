from fastapi import APIRouter

from ..models.core_finance import (
    NpvRequest, NpvResponse, NpvDetail,
    PmtRequest, PmtResponse,
)
from ..core.finance import compute_npv, compute_pmt

router = APIRouter(prefix="/core", tags=["Core Finance"])


@router.post(
    "/npv",
    response_model=NpvResponse,
    summary="Net Present Value",
    description=(
        "Discount a series of dated cashflows back to `settlement_date` using a flat "
        "annual discount rate.\n\n"
        "Each cashflow specifies a `date` and an `amount`. Positive amounts are inflows, "
        "negative amounts are outflows.\n\n"
        "The response includes per-cashflow `discount_factors` and `year_fractions` for "
        "full transparency.\n\n"
        "**Day count conventions:** `ACT/365` (default), `ACT/360`, `30/360`, `ACT/ACT`"
    ),
)
def compute_net_present_value(req: NpvRequest):
    cashflows_raw = [{"date": cf.date, "amount": cf.amount} for cf in req.cashflows]
    result = compute_npv(
        settlement=req.settlement_date,
        cashflows=cashflows_raw,
        discount_rate=req.discount_rate,
        day_count=req.day_count,
    )
    return NpvResponse(
        npv=result["npv"],
        details=NpvDetail(
            discount_factors=result["details"]["discount_factors"],
            year_fractions=result["details"]["year_fractions"],
        ),
    )


@router.post(
    "/pmt",
    response_model=PmtResponse,
    summary="Loan / annuity payment",
    description=(
        "Compute the fixed periodic payment for a fully-amortising loan.\n\n"
        "The number of periods is derived from `start_date`, `end_date`, and `frequency` "
        "(no need to specify periods manually).\n\n"
        "Supported frequencies: `weekly`, `monthly`, `quarterly`, `semi_annual`, `annual`.\n\n"
        "The response includes `payment`, `num_periods`, `total_payment`, and `interest_paid`."
    ),
)
def compute_payment(req: PmtRequest):
    result = compute_pmt(
        principal=req.principal,
        rate=req.rate,
        start_date=req.start_date,
        end_date=req.end_date,
        frequency=req.frequency,
    )
    return PmtResponse(**result)
