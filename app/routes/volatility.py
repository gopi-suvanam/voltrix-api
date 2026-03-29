from fastapi import APIRouter
from ..models.volatility import VolatilityRequest, VolatilityResponse, ConvergenceInfo
from ..core.vol_engine import implied_vol, historical_vol
from ..core.insights import vol_insights

router = APIRouter()


@router.post("/volatility", response_model=VolatilityResponse)
def compute_volatility(req: VolatilityRequest):
    if req.type == "implied":
        sigma, iterations, error, status = implied_vol(
            market_price=req.option_price,
            S=req.spot,
            K=req.strike,
            T=req.time_to_maturity,
            r=req.rate,
            q=req.dividend_yield,
            option_type=req.option_type,
            vol_type=req.vol_type,
            initial_guess=req.initial_guess,
            tolerance=req.tolerance,
            max_iterations=req.max_iterations,
        )
        return VolatilityResponse(
            volatility=round(sigma, 8),
            type="implied",
            convergence=ConvergenceInfo(
                iterations=iterations,
                error=round(error, 10),
                status=status,
            ),
            insights=vol_insights(sigma),
        )

    else:  # historical
        sigma = historical_vol(
            prices=req.prices,
            window=req.window,
            annualization_factor=req.annualization_factor,
            method=req.method,
        )
        return VolatilityResponse(
            volatility=round(sigma, 8),
            type="historical",
            convergence=None,
            insights=vol_insights(sigma),
        )
