from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from app.auth import verify_token
from app.config import settings
from app.routes.options import router as options_router
from app.routes.bonds import router as bonds_router
from app.routes.core_finance import router as core_router

_tags_metadata = [
    {
        "name": "Options",
        "description": (
            "Price European options, compute Greeks, back-solve implied volatility, "
            "and analyse multi-leg strategies. Time-to-expiry is always derived from "
            "`settlement_date` + `expiry_date` — no raw year-fractions required."
        ),
    },
    {
        "name": "Bonds",
        "description": (
            "Price fixed-coupon bonds, solve for yield-to-maturity, and compute "
            "Macaulay duration, modified duration, and convexity. "
            "Coupon schedules and accrued interest are computed from actual dates."
        ),
    },
    {
        "name": "Core Finance",
        "description": (
            "General-purpose financial calculations: "
            "NPV of arbitrary dated cashflow schedules, and fixed-payment loan / annuity sizing (PMT)."
        ),
    },
]

app = FastAPI(
    title="Voltrix API",
    description=(
        "A unified financial computation engine with time-aware modelling.\n\n"
        "## Authentication\n"
        "All endpoints require a Bearer token in the `Authorization` header:\n"
        "```\nAuthorization: Bearer <token>\n```\n"
        "Auth is disabled when `API_TOKEN_HASH` is not configured (development mode).\n\n"
        "## Date inputs\n"
        "All endpoints accept ISO-8601 date strings (`YYYY-MM-DD`). "
        "Time-to-maturity / time-to-expiry is never a raw float — it is always computed from "
        "`settlement_date` and `maturity_date` / `expiry_date` using the specified "
        "`day_count` convention.\n\n"
        "## Volatility input (options)\n"
        "The `volatility` field accepts a scalar (e.g. `0.2` for 20%) or a full "
        "`VolatilityInput` object supporting constant or bilinear-interpolated "
        "matrix (vol-surface) configurations."
    ),
    version="2.0.0",
    openapi_tags=_tags_metadata,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_auth = [Depends(verify_token)]

_v = settings.api_version

app.include_router(options_router, prefix=f"/{_v}", dependencies=_auth)
app.include_router(bonds_router,   prefix=f"/{_v}", dependencies=_auth)
app.include_router(core_router,    prefix=f"/{_v}", dependencies=_auth)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if isinstance(exc.detail, dict):
        return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": str(exc.status_code), "message": exc.detail}},
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    first = errors[0] if errors else {}
    msg = first.get("msg", "Validation error")
    msg = msg.removeprefix("Value error, ")
    return JSONResponse(
        status_code=422,
        content={"error": {"code": "INVALID_INPUT", "message": msg}},
    )


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    return JSONResponse(
        status_code=400,
        content={"error": {"code": "INVALID_INPUT", "message": str(exc)}},
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"error": {"code": "INTERNAL_ERROR", "message": "An unexpected error occurred"}},
    )


@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok", "service": "Voltrix API", "version": "2.0.0"}


@app.get("/docs.md", include_in_schema=False)
def serve_docs():
    return FileResponse("docs.md", media_type="text/markdown")
