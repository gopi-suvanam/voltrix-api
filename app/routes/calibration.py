from fastapi import APIRouter, HTTPException

from ..models.calibration import (
    SABRCalibrationRequest, SABRCalibrationResponse,
    SVICalibrationRequest, SVICalibrationResponse,
    HestonCalibrationRequest, HestonCalibrationResponse,
    CEVCalibrationRequest, CEVCalibrationResponse,
    CalibrationRequest,
)
from ..core.calibration import calibrate_sabr, calibrate_svi, calibrate_heston, calibrate_cev
from ..core.day_count import year_fraction

router = APIRouter(prefix="/options/calibration", tags=["Calibration"])


def _build_observations(req: CalibrationRequest) -> list[dict]:
    """Convert request observations to core-layer dicts with T computed from dates."""
    result = []
    for i, obs in enumerate(req.observations):
        T = year_fraction(req.settlement_date, obs.expiry_date, req.day_count)
        if T <= 0:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "INVALID_INPUT",
                    "message": f"observations[{i}].expiry_date must be after settlement_date",
                },
            )
        result.append({
            "strike": obs.strike,
            "T": T,
            "option_type": obs.option_type,
            "market_price": obs.market_price,
        })
    return result


@router.post(
    "/sabr",
    response_model=SABRCalibrationResponse,
    summary="Calibrate SABR parameters",
    description=(
        "Fit Hagan et al. (2002) SABR parameters **(α, ρ, ν)** to a set of observed market "
        "option prices. The elasticity exponent **β** is fixed by the caller.\n\n"
        "**Algorithm:** The calibrator back-solves each market price to a Black-Scholes "
        "implied vol, then minimises the sum of squared SABR-vs-market vol errors using "
        "L-BFGS-B with multiple starting points.\n\n"
        "**Minimum observations:** 3 options with distinct strikes.\n\n"
        "The calibrated parameters can be passed directly into any `/options/*` endpoint "
        "via `volatility.surface_type='sabr'` and `volatility.other_params`."
    ),
)
def calibrate_sabr_endpoint(req: SABRCalibrationRequest):
    obs = _build_observations(req)
    try:
        result = calibrate_sabr(obs, req.spot, req.rate, req.dividend_yield, req.beta)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"code": "CALIBRATION_ERROR", "message": str(exc)})
    return SABRCalibrationResponse(**result)


@router.post(
    "/svi",
    response_model=SVICalibrationResponse,
    summary="Calibrate SVI parameters",
    description=(
        "Fit Gatheral (2004) raw SVI parameters **(a, b, ρ, m, σ)** to observed market "
        "option prices at a single maturity or across maturities.\n\n"
        "**Algorithm:** Back-solves market prices to Black-Scholes implied vols, then "
        "minimises squared SVI-vs-market vol errors with the butterfly-arbitrage-free "
        "constraint `a + b·σ·√(1−ρ²) ≥ 0` enforced.\n\n"
        "**Minimum observations:** 4 options with distinct strikes.\n\n"
        "Calibrated parameters can be used in `volatility.surface_type='svi'`."
    ),
)
def calibrate_svi_endpoint(req: SVICalibrationRequest):
    obs = _build_observations(req)
    try:
        result = calibrate_svi(obs, req.spot, req.rate, req.dividend_yield)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"code": "CALIBRATION_ERROR", "message": str(exc)})
    return SVICalibrationResponse(**result)


@router.post(
    "/heston",
    response_model=HestonCalibrationResponse,
    summary="Calibrate Heston parameters",
    description=(
        "Fit Heston (1993) stochastic-volatility model parameters **(v₀, κ, θ, σᵥ, ρ)** "
        "to observed market option prices.\n\n"
        "**Algorithm:** Optimises directly in price space (not implied-vol space) using "
        "differential evolution for global search followed by L-BFGS-B refinement. "
        "The semi-analytic characteristic-function pricer is used throughout.\n\n"
        "**Minimum observations:** 5 options (ideally spanning multiple strikes and maturities).\n\n"
        "**Feller condition:** `2κθ > σᵥ²` ensures variance stays strictly positive; "
        "the response reports whether this is satisfied.\n\n"
        "Calibrated parameters can be used with `model='heston'` and "
        "`volatility.surface_type='heston'`."
    ),
)
def calibrate_heston_endpoint(req: HestonCalibrationRequest):
    obs = _build_observations(req)
    try:
        result = calibrate_heston(obs, req.spot, req.rate, req.dividend_yield)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"code": "CALIBRATION_ERROR", "message": str(exc)})
    return HestonCalibrationResponse(**result)


@router.post(
    "/cev",
    response_model=CEVCalibrationResponse,
    summary="Calibrate CEV parameters",
    description=(
        "Fit Constant Elasticity of Variance (CEV) model parameters **(σ, β)** to observed "
        "market option prices.\n\n"
        "**Algorithm:** Back-solves market prices to Black-Scholes implied vols, then fits "
        "using the Hagan-Woodward (1999) analytic CEV-to-BS vol approximation — avoiding "
        "slow Monte Carlo during optimisation.\n\n"
        "**β interpretation:** β=1 → log-normal (Black-Scholes), β=0.5 → square-root "
        "process, β=0 → normal/absolute model.\n\n"
        "**Minimum observations:** 2 options with distinct strikes.\n\n"
        "Calibrated **σ** (CEV vol level) and **β** can be used in `model='cev'` pricing "
        "via `other_params: {cev_beta: <beta>}` with `volatility` set to the calibrated σ."
    ),
)
def calibrate_cev_endpoint(req: CEVCalibrationRequest):
    obs = _build_observations(req)
    try:
        result = calibrate_cev(obs, req.spot, req.rate, req.dividend_yield)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"code": "CALIBRATION_ERROR", "message": str(exc)})
    return CEVCalibrationResponse(**result)
