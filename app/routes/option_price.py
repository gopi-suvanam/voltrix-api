from fastapi import APIRouter
from ..models.option_price import OptionPriceRequest, OptionPriceResponse, OptionPriceInputs
from ..models.common import VolatilityUsed
from ..core.vol_surface import resolve_vol
from ..core.pricing import price_option
from ..core.insights import option_price_insights

router = APIRouter()


@router.post("/option-price", response_model=OptionPriceResponse)
def compute_option_price(req: OptionPriceRequest):
    vol_dict = req.volatility.model_dump()
    beta = vol_dict.get("other_params", {}).get("cev_beta", 1.0)

    sigma, source, surface_type = resolve_vol(vol_dict, req.strike, req.time_to_maturity)

    price = price_option(
        model=req.model,
        option_type=req.option_type,
        S=req.spot,
        K=req.strike,
        T=req.time_to_maturity,
        r=req.rate,
        q=req.dividend_yield,
        sigma=sigma,
        beta=beta,
        num_simulations=req.num_simulations,
        seed=req.seed,
    )

    insights = None
    if req.include_insights:
        insights = option_price_insights(req.spot, req.strike, sigma, vol_dict)

    return OptionPriceResponse(
        price=round(price, 6),
        model_used=req.model,
        volatility_used=VolatilityUsed(
            value=round(sigma, 6),
            source=source,
            surface_type=surface_type,
        ),
        inputs=OptionPriceInputs(
            spot=req.spot,
            strike=req.strike,
            time_to_maturity=req.time_to_maturity,
        ),
        insights=insights,
    )
