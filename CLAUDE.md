# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run the development server
uvicorn main:app --reload

# Run with a specific host/port
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Install dependencies
pip install -r requirements.txt

# Generate an API token for authentication
python generate_token.py
```

There is no test suite in this repository. Validation is done via Pydantic models and the interactive API docs at `/docs`.

## Authentication

Auth is disabled by default (development mode). To enable it:
1. Run `python generate_token.py` to get a token + SHA-256 hash
2. Create `config.env` in the project root with `API_TOKEN_HASH=<hash>`
3. Pass `Authorization: Bearer <token>` in requests

Auth is implemented in `app/auth.py` as a FastAPI dependency injected on all three routers in `main.py`.

## Architecture

The API is a FastAPI application with three domains:

| Domain | Router | Models | Core Logic |
|---|---|---|---|
| Options | `app/routes/options.py` | `app/models/options.py` | `app/core/{pricing,greeks,vol_engine,vol_surface,strategies,insights}.py` |
| Bonds | `app/routes/bonds.py` | `app/models/bonds.py` | `app/core/{bond_math,day_count}.py` |
| Core Finance | `app/routes/core_finance.py` | `app/models/core_finance.py` | `app/core/finance.py` |

Shared Pydantic models (error responses, `VolatilityInput`) live in `app/models/common.py`.

### Request Flow

```
POST /options/price
  → Pydantic validation (options.py models)
    → route handler calls core function (pricing.py)
      → vol resolved via vol_surface.py
        → day count via day_count.py
          → response + insights (insights.py)
```

### Volatility Resolution Pipeline

`VolatilityInput` (defined in `app/models/common.py`) supports two surface types:
- **constant**: Single scalar value
- **matrix**: Strike × maturity grid with bilinear interpolation (flat extrapolation at boundaries)

Routes accept `volatility` as either a plain scalar (auto-coerced to `VolatilityInput`) or a full `VolatilityInput` object. Resolution always flows through `app/core/vol_surface.py:resolve_vol()`.

### Day Count Conventions

Implemented in `app/core/day_count.py`. Supported: `ACT/365`, `ACT/360`, `30/360`, `ACT/ACT`. All date math flows through `year_fraction(start, end, convention)`.

### Pricing Models

| Model | Key | Notes |
|---|---|---|
| Black-Scholes | `black_scholes` | Log-normal; analytic Greeks available |
| Bachelier | `bachelier` | Normal model |
| CEV | `cev` | Monte Carlo only when beta ≠ 1 |
| Monte Carlo | `monte_carlo` | GBM discretization; controlled via `num_simulations`, `seed` |

Greeks default to analytic (Black-Scholes only) or numerical finite-difference for other models.

### Bond Math

`app/core/bond_math.py` generates coupon schedules backward from maturity, computes accrued interest from the last coupon date, and solves YTM via Newton-Raphson with numerical derivatives.

### Strategy Analysis

`app/core/strategies.py` evaluates multi-leg option strategies over a 400-point payoff grid. Breakevens are detected via zero-crossings. Strategy type is classified by `identify_strategy()`.

## Configuration

`app/config.py` uses Pydantic `BaseSettings` reading from `config.env`:
- `API_TOKEN_HASH`: SHA-256 hash of bearer token (empty = auth disabled)
