from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from app.auth import verify_token
from app.routes import option_price, greeks, volatility

app = FastAPI(
    title="QuantForge API",
    description="Quantitative finance computation engine — options pricing, Greeks, volatility analytics",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_auth = [Depends(verify_token)]

app.include_router(option_price.router, dependencies=_auth)
app.include_router(greeks.router,       dependencies=_auth)
app.include_router(volatility.router,   dependencies=_auth)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    # detail is already {"code": ..., "message": ...} when raised from verify_token
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
    # Strip pydantic's "Value error, " prefix if present
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


@app.get("/health")
def health():
    return {"status": "ok", "service": "QuantForge API", "version": "1.0.0"}
