from fastapi import APIRouter
from ..models.greeks import GreeksRequest, GreeksResponse, GreeksUnits
from ..models.common import VolatilityUsed
from ..core.vol_surface import resolve_vol
from ..core.greeks import compute_greeks
from ..core.insights import greeks_insights

router = APIRouter()


@router.post("/greeks", response_model=GreeksResponse)
def compute_greeks_endpoint(req: GreeksRequest):
    vol_dict = req.volatility.model_dump()
    beta = vol_dict.get("other_params", {}).get("cev_beta", 1.0)

    sigma, source, surface_type = resolve_vol(vol_dict, req.strike, req.time_to_maturity)

    # Force finite_difference when using a vol surface or a non-BS model
    method = req.method
    if surface_type == "matrix" or req.model != "black_scholes":
        method = "finite_difference"

    greeks = compute_greeks(
        model=req.model,
        option_type=req.option_type,
        S=req.spot,
        K=req.strike,
        T=req.time_to_maturity,
        r=req.rate,
        q=req.dividend_yield,
        sigma=sigma,
        method=method,
        bump_size=req.bump_size,
        beta=beta,
        num_simulations=req.num_simulations,
        seed=req.seed,
    )

    interpretation = None
    if req.include_insights:
        interpretation = greeks_insights(greeks["delta"], greeks["vega"], greeks["theta"])

    return GreeksResponse(
        delta=greeks["delta"],
        gamma=greeks["gamma"],
        vega=greeks["vega"],
        theta=greeks["theta"],
        rho=greeks["rho"],
        units=GreeksUnits(),
        volatility_used=VolatilityUsed(
            value=round(sigma, 6),
            source=source,
            surface_type=surface_type,
        ),
        interpretation=interpretation,
    )
