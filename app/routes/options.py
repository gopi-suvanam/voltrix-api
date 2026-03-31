from fastapi import APIRouter

from ..models.options import (
    OptionPriceRequest, OptionPriceResponse,
    GreeksRequest, GreeksResponse, GreeksUnits,
    VolatilityRequest, VolatilityResponse, ConvergenceInfo,
    StrategyRequest, StrategyResponse,
)
from ..models.common import VolatilityUsed
from ..core.day_count import year_fraction
from ..core.vol_surface import resolve_vol
from ..core.pricing import price_option
from ..core.greeks import compute_greeks
from ..core.vol_engine import implied_vol, historical_vol
from ..core.insights import option_price_insights, greeks_insights, vol_insights
from ..core.strategies import analyze_strategy

router = APIRouter(prefix="/options", tags=["Options"])


@router.post(
    "/price",
    response_model=OptionPriceResponse,
    summary="Price a European option",
    description=(
        "Compute the fair value of a European call or put using the selected model.\n\n"
        "**Models:** `black_scholes`, `bachelier`, `normal`, `cev`, `monte_carlo`\n\n"
        "Time to expiry is derived from `settlement_date` and `expiry_date` using the "
        "specified `day_count` convention.\n\n"
        "The `volatility` field accepts a scalar (e.g. `0.2`) or a full `VolatilityInput` "
        "object supporting constant or bilinear-interpolated matrix surfaces.\n\n"
        "Set `include_insights: true` for a plain-language interpretation."
    ),
)
def compute_option_price(req: OptionPriceRequest):
    T = year_fraction(req.settlement_date, req.expiry_date, req.day_count)
    vol_dict = req.volatility.model_dump()
    other = vol_dict.get("other_params", {})
    beta = other.get("cev_beta", 1.0)
    sigma, source, surface_type = resolve_vol(
        vol_dict, req.strike, T, S=req.spot, r=req.rate, q=req.dividend_yield
    )

    heston_params = None
    if req.model == "heston":
        heston_params = {
            "v0":      float(other.get("v0", 0.04)),
            "kappa":   float(other.get("kappa", 2.0)),
            "theta":   float(other.get("theta", 0.04)),
            "sigma_v": float(other.get("sigma_v", 0.3)),
            "rho":     float(other.get("rho", -0.7)),
            "use_mc":  bool(other.get("use_mc", False)),
        }

    price = price_option(
        model=req.model,
        option_type=req.option_type,
        S=req.spot,
        K=req.strike,
        T=T,
        r=req.rate,
        q=req.dividend_yield,
        sigma=sigma,
        beta=beta,
        num_simulations=req.num_simulations,
        seed=req.seed,
        heston_params=heston_params,
    )

    insights = None
    if req.include_insights:
        insights = option_price_insights(req.spot, req.strike, sigma, vol_dict)

    days = (req.expiry_date - req.settlement_date).days

    return OptionPriceResponse(
        price=round(price, 6),
        time_to_expiry_days=days,
        model_used=req.model,
        volatility_used=VolatilityUsed(
            value=round(sigma, 6),
            source=source,
            surface_type=surface_type,
        ),
        insights=insights,
    )


@router.post(
    "/greeks",
    response_model=GreeksResponse,
    summary="Compute option Greeks",
    description=(
        "Calculate delta, gamma, vega, theta, and rho for a European option.\n\n"
        "| Greek | Measures |\n"
        "|-------|----------|\n"
        "| **delta** | Price sensitivity to spot |\n"
        "| **gamma** | Delta sensitivity to spot |\n"
        "| **vega** | Price sensitivity per 1% vol change |\n"
        "| **theta** | Time decay per calendar day |\n"
        "| **rho** | Price sensitivity per 1% rate change |\n\n"
        "`analytic` method uses closed-form Black-Scholes derivatives. "
        "`finite_difference` uses bump-and-reprice and works with all models. "
        "A vol surface or non-Black-Scholes model forces `finite_difference` automatically."
    ),
)
def compute_greeks_endpoint(req: GreeksRequest):
    T = year_fraction(req.settlement_date, req.expiry_date, req.day_count)
    vol_dict = req.volatility.model_dump()
    other = vol_dict.get("other_params", {})
    beta = other.get("cev_beta", 1.0)
    sigma, source, surface_type = resolve_vol(
        vol_dict, req.strike, T, S=req.spot, r=req.rate, q=req.dividend_yield
    )

    method = req.method
    # Parametric surfaces and Heston always require finite-difference Greeks
    if surface_type in ("matrix", "sabr", "svi", "heston") or req.model != "black_scholes":
        method = "finite_difference"

    heston_params = None
    if req.model == "heston":
        heston_params = {
            "v0":      float(other.get("v0", 0.04)),
            "kappa":   float(other.get("kappa", 2.0)),
            "theta":   float(other.get("theta", 0.04)),
            "sigma_v": float(other.get("sigma_v", 0.3)),
            "rho":     float(other.get("rho", -0.7)),
            "use_mc":  bool(other.get("use_mc", False)),
        }

    greeks = compute_greeks(
        model=req.model,
        option_type=req.option_type,
        S=req.spot,
        K=req.strike,
        T=T,
        r=req.rate,
        q=req.dividend_yield,
        sigma=sigma,
        method=method,
        bump_size=req.bump_size,
        beta=beta,
        num_simulations=req.num_simulations,
        seed=req.seed,
        heston_params=heston_params,
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


@router.post(
    "/volatility",
    response_model=VolatilityResponse,
    summary="Compute implied or historical volatility",
    description=(
        "**`implied`** — Newton-Raphson solver to back out the vol that prices a "
        "Black-Scholes (log-normal) or Bachelier (normal) option to the observed market price. "
        "Requires: `option_price`, `option_type`, `spot`, `strike`, `rate`, `settlement_date`, `expiry_date`.\n\n"
        "**`historical`** — Realised vol from a price series, annualised by `annualization_factor`. "
        "Requires: `prices` (≥ 2 values)."
    ),
)
def compute_volatility(req: VolatilityRequest):
    if req.type == "implied":
        T = year_fraction(req.settlement_date, req.expiry_date, req.day_count)
        days = (req.expiry_date - req.settlement_date).days
        sigma, iterations, error, status = implied_vol(
            market_price=req.option_price,
            S=req.spot,
            K=req.strike,
            T=T,
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
            time_to_expiry_days=days,
            convergence=ConvergenceInfo(
                iterations=iterations,
                error=round(error, 10),
                status=status,
            ),
            insights=vol_insights(sigma),
        )
    else:
        sigma = historical_vol(
            prices=req.prices,
            window=req.window,
            annualization_factor=req.annualization_factor,
            method=req.method,
        )
        return VolatilityResponse(
            volatility=round(sigma, 8),
            type="historical",
            time_to_expiry_days=None,
            convergence=None,
            insights=vol_insights(sigma),
        )


@router.post(
    "/strategies",
    response_model=StrategyResponse,
    summary="Analyze a multi-leg option strategy",
    description=(
        "Compute the payoff profile, max profit/loss, and breakevens for a multi-leg "
        "option strategy at expiry.\n\n"
        "Each leg specifies `type`, `position`, `strike`, `expiry_date`, and the `premium` "
        "paid or received.\n\n"
        "**Auto-identified strategies** include: long/short call/put, bull/bear call spread, "
        "bull/bear put spread, straddle, strangle, butterfly, iron condor, and custom.\n\n"
        "`max_profit` / `max_loss` are `null` for theoretically unlimited payoffs "
        "(e.g. naked long call)."
    ),
)
def analyze_option_strategy(req: StrategyRequest):
    legs_raw = [
        {
            "type": leg.type,
            "position": leg.position,
            "strike": leg.strike,
            "expiry_date": str(leg.expiry_date),
            "premium": leg.premium,
        }
        for leg in req.legs
    ]

    result = analyze_strategy(legs_raw, req.spot)

    return StrategyResponse(
        strategy=result["strategy"],
        max_profit=result["max_profit"],
        max_loss=result["max_loss"],
        breakevens=result["breakevens"],
        payoff=[{"spot": p["spot"], "value": p["value"]} for p in result["payoff"]],
    )
