# Voltrix API

A quantitative finance computation engine exposed as a REST API. Built with FastAPI.

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/v2/options/price` | Price options (BS, Bachelier, CEV, Monte Carlo, Heston) |
| POST | `/v2/options/greeks` | Compute option Greeks (analytic or finite-difference) |
| POST | `/v2/options/volatility` | Implied vol (Newton-Raphson) or historical vol |
| POST | `/v2/options/strategies` | Multi-leg strategy payoff analysis |
| POST | `/v2/bonds/price` | Bond dirty/clean price from YTM |
| POST | `/v2/bonds/yield` | YTM from clean price |
| POST | `/v2/bonds/sensitivity` | Duration and convexity |
| POST | `/v2/core/npv` | Discounted cashflow NPV |
| POST | `/v2/core/pmt` | Periodic loan payment |
| GET  | `/health` | Health check |

Interactive docs: `http://localhost:8000/docs` (Swagger) · `http://localhost:8000/redoc`

Full reference: [`docs.md`](docs.md)

---

## Setup

```bash
# Create and activate virtual environment
python -m venv .env
.env\Scripts\activate        # Windows
# source .env/bin/activate   # macOS/Linux

# Install dependencies
pip install -r requirements.txt

# Run the server
uvicorn main:app --reload
```

---

## Supported Pricing Models

| Model | Key | Method | Notes |
|-------|-----|--------|-------|
| Black-Scholes | `black_scholes` | Analytic | Log-normal; analytic Greeks |
| Bachelier | `bachelier` | Analytic | Normal model |
| CEV | `cev` | Monte Carlo | `dS = (r−q)S dt + σSᵝ dW`; set `cev_beta` in `other_params` |
| GBM Monte Carlo | `monte_carlo` | Monte Carlo | Exact GBM simulation |
| Heston | `heston` | Semi-analytic / MC | Stochastic variance; requires Heston surface params |

---

## Volatility Surfaces

The `volatility` field accepts a plain scalar (e.g. `0.2`) or a `VolatilityInput` object with five
surface types:

### Constant

```json
"volatility": 0.2
```

### Matrix (bilinear interpolation)

```json
{
  "surface_type": "matrix",
  "data": {
    "strikes":    [90, 100, 110],
    "maturities": [0.5, 1.0],
    "vol_matrix": [
      [0.25, 0.24],
      [0.20, 0.19],
      [0.22, 0.21]
    ]
  }
}
```

### SABR (Hagan et al. 2002)

Parametric smile via the SABR formula. Resolves to an implied BS vol at (K, T).

```json
{
  "surface_type": "sabr",
  "other_params": { "alpha": 0.3, "beta": 0.5, "rho": -0.3, "nu": 0.4 }
}
```

| Param | Description |
|-------|-------------|
| `alpha` | Initial vol level (> 0) |
| `beta` | CEV exponent 0–1. `1` = log-normal backbone |
| `rho` | Spot-vol correlation. Negative → downside skew |
| `nu` | Vol of vol (≥ 0) |

### SVI (Gatheral 2004 raw parametrisation)

Total implied variance as a function of log-moneyness: `w(k) = a + b·(ρ·(k−m) + √((k−m)² + σ²))`.

```json
{
  "surface_type": "svi",
  "other_params": { "a": 0.04, "b": 0.2, "rho": -0.3, "m": 0.0, "sigma": 0.3 }
}
```

### Heston (1993 stochastic-vol)

Use with `"model": "heston"` for semi-analytic (characteristic function) or MC pricing.

```json
{
  "surface_type": "heston",
  "other_params": {
    "v0": 0.04, "kappa": 2.0, "theta": 0.04, "sigma_v": 0.3, "rho": -0.7
  }
}
```

Add `"use_mc": true` to `other_params` to use Monte Carlo instead of the semi-analytic integrator.

| Param | Description |
|-------|-------------|
| `v0` | Initial variance (initial vol ≈ √v₀) |
| `kappa` | Mean-reversion speed |
| `theta` | Long-run variance (long-run vol ≈ √θ) |
| `sigma_v` | Volatility of variance |
| `rho` | Spot-variance correlation. Negative → left skew |

---

## Authentication

Disabled by default. To enable:

1. `python generate_token.py` → copy the hash
2. Create `config.env`: `API_TOKEN_HASH=<hash>`
3. Pass `Authorization: Bearer <token>` in all requests

---

## Project Structure

```
voltrix-api/
├── main.py                      # App entry point, versioned routers, error handlers
├── requirements.txt
├── generate_token.py
├── docs.md                      # Full API reference
├── app/
│   ├── config.py                # Pydantic settings (reads config.env)
│   ├── auth.py                  # Bearer token dependency
│   ├── core/
│   │   ├── pricing.py           # BS, Bachelier, CEV, GBM MC, Heston dispatch
│   │   ├── heston.py            # Heston semi-analytic (CF) + MC pricer
│   │   ├── sabr.py              # Hagan SABR implied-vol formula
│   │   ├── svi.py               # Gatheral raw SVI total-variance smile
│   │   ├── greeks.py            # Analytic BS Greeks + finite-difference bump-reprice
│   │   ├── vol_surface.py       # Vol resolution: constant, matrix, SABR, SVI, Heston
│   │   ├── vol_engine.py        # Implied vol (Newton-Raphson), historical vol
│   │   ├── strategies.py        # Multi-leg strategy payoff + breakeven analysis
│   │   ├── insights.py          # Plain-language result interpretation
│   │   ├── bond_math.py         # Coupon schedule, accrued interest, YTM solver
│   │   ├── day_count.py         # ACT/365, ACT/360, 30/360, ACT/ACT year fractions
│   │   └── finance.py           # NPV, PMT core computations
│   ├── models/
│   │   ├── common.py            # VolatilityInput, VolData, VolatilityUsed, ErrorResponse
│   │   ├── options.py           # Option price / greeks / vol / strategy request+response
│   │   ├── bonds.py             # Bond request+response models
│   │   └── core_finance.py      # NPV / PMT request+response models
│   └── routes/
│       ├── options.py           # /v2/options/* handlers
│       ├── bonds.py             # /v2/bonds/* handlers
│       └── core_finance.py      # /v2/core/* handlers
```
