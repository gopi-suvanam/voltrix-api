# QuantForge API

A quantitative finance computation engine exposed as a REST API. Built with FastAPI.

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/option-price` | Price options (BS, Bachelier, CEV, Monte Carlo) |
| POST | `/greeks` | Compute option Greeks (analytic or finite difference) |
| POST | `/volatility` | Implied vol (Newton-Raphson) or historical vol |
| GET | `/health` | Health check |

Interactive docs available at `http://localhost:8000/docs` once the server is running.

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

## Supported Models

| Model | Key | Notes |
|-------|-----|-------|
| Black-Scholes | `black_scholes` | Log-normal, analytical |
| Bachelier | `bachelier` | Normal model, analytical |
| CEV | `cev` | Monte Carlo with time-stepping |
| Monte Carlo | `monte_carlo` | Exact GBM simulation |

## Volatility Input

All endpoints accept a unified volatility object:

```json
{
  "vol_type": "log_normal",
  "surface_type": "constant",
  "data": { "vol": 0.2 }
}
```

Or as a bare scalar (auto-converted to constant):

```json
"volatility": 0.2
```

### Matrix Surface (bilinear interpolation)

```json
{
  "vol_type": "log_normal",
  "surface_type": "matrix",
  "data": {
    "strikes":    [90, 100, 110],
    "maturities": [0.5, 1.0],
    "vol_matrix": [
      [0.25, 0.24],
      [0.20, 0.19],
      [0.22, 0.21]
    ]
  },
  "interpolation": "bilinear",
  "extrapolation": "flat"
}
```

`vol_matrix[i][j]` = volatility at `strikes[i]`, `maturities[j]`.

---

## API Reference

### POST `/option-price`

```json
{
  "model": "black_scholes",
  "option_type": "call",
  "spot": 100,
  "strike": 105,
  "rate": 0.05,
  "time_to_maturity": 0.75,
  "dividend_yield": 0.0,
  "volatility": { "surface_type": "constant", "data": { "vol": 0.2 } },
  "num_simulations": 10000,
  "seed": 42,
  "include_insights": true
}
```

**Response**

```json
{
  "price": 6.387,
  "model_used": "black_scholes",
  "volatility_used": { "value": 0.2, "source": "constant", "surface_type": "constant" },
  "inputs": { "spot": 100, "strike": 105, "time_to_maturity": 0.75 },
  "insights": { "moneyness": "out_of_the_money", "vol_regime": "normal" }
}
```

---

### POST `/greeks`

```json
{
  "model": "black_scholes",
  "option_type": "call",
  "spot": 100,
  "strike": 100,
  "rate": 0.05,
  "time_to_maturity": 1.0,
  "volatility": { "surface_type": "constant", "data": { "vol": 0.2 } },
  "method": "analytic",
  "bump_size": 0.01,
  "include_insights": true
}
```

`method`: `analytic` (BS only) or `finite_difference`. When a vol surface or non-BS model is used, finite differences are applied automatically.

**Response**

```json
{
  "delta": 0.6368,
  "gamma": 0.0188,
  "vega": 0.3752,
  "theta": -0.0176,
  "rho": 0.5323,
  "units": { "vega": "per 1% vol change", "theta": "per day decay" },
  "volatility_used": { "value": 0.2, "source": "constant", "surface_type": "constant" },
  "interpretation": {
    "delta": "High directional exposure",
    "vega": "Highly sensitive to volatility",
    "theta": "Time decay moderate"
  }
}
```

---

### POST `/volatility`

**Implied volatility** (Newton-Raphson + bisection fallback)

```json
{
  "type": "implied",
  "option_price": 10.45,
  "option_type": "call",
  "spot": 100,
  "strike": 100,
  "rate": 0.05,
  "time_to_maturity": 1.0,
  "vol_type": "log_normal",
  "initial_guess": 0.2,
  "tolerance": 1e-6,
  "max_iterations": 100
}
```

**Historical volatility**

```json
{
  "type": "historical",
  "prices": [100, 102, 101, 105, 107],
  "method": "log_returns",
  "window": 5,
  "annualization_factor": 252
}
```

**Response**

```json
{
  "volatility": 0.19998445,
  "type": "implied",
  "convergence": { "iterations": 2, "error": 1.2e-9, "status": "converged" },
  "insights": { "vol_regime": "normal", "relative_level": "near_historical_avg" }
}
```

---

## Error Format

All errors follow a consistent structure:

```json
{
  "error": {
    "code": "INVALID_INPUT",
    "message": "'spot' must be > 0"
  }
}
```

---

## Performance Targets

| Endpoint | Target |
|----------|--------|
| `/option-price` (BS) | < 50ms |
| `/greeks` (analytic) | < 50ms |
| `/option-price` (Monte Carlo) | < 300ms |
| `/volatility` (implied) | < 100ms |

---

## Project Structure

```
quantforge-api/
├── main.py                   # App entry point, error handlers
├── requirements.txt
├── app/
│   ├── core/
│   │   ├── pricing.py        # BS, Bachelier, Monte Carlo, CEV
│   │   ├── greeks.py         # Analytic + numerical Greeks
│   │   ├── vol_surface.py    # Vol surface bilinear interpolation
│   │   ├── vol_engine.py     # Implied vol (NR + bisection), historical vol
│   │   └── insights.py       # Moneyness, vol regime, skew detection
│   ├── models/
│   │   ├── common.py         # Shared Pydantic models
│   │   ├── option_price.py
│   │   ├── greeks.py
│   │   └── volatility.py
│   └── routes/
│       ├── option_price.py
│       ├── greeks.py
│       └── volatility.py
```
