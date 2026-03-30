# Voltrix API — Reference

**Version:** 2.0.0
**Base URL:** `http://localhost:8000/v2`
**Interactive UI:** `http://localhost:8000/docs` (Swagger)

---

## Authentication

Auth is **disabled by default** (development mode). To enable it, create `config.env`:

```
API_TOKEN_HASH=<sha256-hex-of-your-token>
```

Generate a token with:

```bash
python generate_token.py
```

When auth is active, every request must include:

```
Authorization: Bearer <token>
```

---

## Common Types

### VolatilityInput

Used in `/v2/options/price` and `/v2/options/greeks` as the `volatility` field.
Accepts either a **plain scalar** (e.g. `0.2`) or a full object:

```json
{
  "vol_type":      "log_normal",
  "surface_type":  "constant",
  "data":          { "vol": 0.2 },
  "interpolation": "bilinear",
  "extrapolation": "flat",
  "other_params":  {}
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `vol_type` | `log_normal` \| `normal` \| `cev` | `log_normal` | Vol convention |
| `surface_type` | `constant` \| `matrix` | `constant` | Flat vol or interpolated surface |
| `data` | object | — | See below |
| `interpolation` | `bilinear` | `bilinear` | Matrix interpolation method |
| `extrapolation` | `flat` | `flat` | Behaviour outside surface bounds |
| `other_params` | object | `{}` | Model-specific params. CEV: `{ "cev_beta": 0.5 }` |

**`data` for `surface_type: "constant"`**

```json
{ "vol": 0.2 }
```

**`data` for `surface_type: "matrix"`**

```json
{
  "strikes":    [90, 100, 110],
  "maturities": [0.5, 1.0],
  "vol_matrix": [
    [0.25, 0.24],
    [0.20, 0.19],
    [0.22, 0.21]
  ]
}
```

`vol_matrix[i][j]` is the vol at `strikes[i]` and `maturities[j]` (maturities in **year fractions**).

---

### Day Count Conventions

| Value | Description |
|-------|-------------|
| `ACT/365` | Actual days / 365 (default for options) |
| `ACT/360` | Actual days / 360 |
| `30/360` | 30-day months, 360-day year (default for bonds) |
| `ACT/ACT` | Actual/Actual ISDA |

---

### Cashflow

Used in `/v2/core/npv`:

```json
{ "date": "2026-06-01", "amount": 50.0 }
```

Positive = inflow, negative = outflow.

---

### Error Response

All errors follow this shape:

```json
{
  "error": {
    "code":    "INVALID_INPUT",
    "message": "expiry_date must be after settlement_date"
  }
}
```

| HTTP Status | Code | Cause |
|-------------|------|-------|
| 400 | `INVALID_INPUT` | Business logic error (e.g. price below intrinsic) |
| 401 | `UNAUTHORIZED` | Missing or invalid Bearer token |
| 422 | `INVALID_INPUT` | Request body validation failure |
| 500 | `INTERNAL_ERROR` | Unexpected server error |

---

## /v2/options

### POST /v2/options/price

Price a European call or put option.

**Models**

| `model` | Description |
|---------|-------------|
| `black_scholes` | Closed-form Black-Scholes-Merton (default) |
| `bachelier` | Closed-form Bachelier (normal vol) |
| `cev` | CEV via Monte Carlo; set `cev_beta` in `volatility.other_params` |
| `monte_carlo` | Risk-neutral GBM simulation |

**Request**

```json
{
  "model":           "black_scholes",
  "option_type":     "call",
  "spot":            100,
  "strike":          105,
  "rate":            0.05,
  "dividend_yield":  0.0,
  "settlement_date": "2026-01-01",
  "expiry_date":     "2027-01-01",
  "day_count":       "ACT/365",
  "volatility":      0.2,
  "num_simulations": 10000,
  "seed":            null,
  "include_insights": false
}
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `model` | string | | `black_scholes` | Pricing model |
| `option_type` | `call` \| `put` | | `call` | Option right |
| `spot` | float > 0 | ✓ | — | Current underlying price |
| `strike` | float > 0 | ✓ | — | Strike price |
| `rate` | float | ✓ | — | Continuous risk-free rate (e.g. `0.05`) |
| `dividend_yield` | float | | `0.0` | Continuous dividend yield |
| `settlement_date` | date | ✓ | — | Valuation date (`YYYY-MM-DD`) |
| `expiry_date` | date | ✓ | — | Expiry date (`YYYY-MM-DD`) |
| `day_count` | string | | `ACT/365` | Day count convention |
| `volatility` | float \| VolatilityInput | ✓ | — | Scalar or vol surface |
| `num_simulations` | int | | `10000` | MC paths (Monte Carlo only) |
| `seed` | int \| null | | `null` | RNG seed for reproducible MC |
| `include_insights` | bool | | `false` | Add plain-language interpretation |

**Response**

```json
{
  "price":              8.73,
  "time_to_expiry_days": 365,
  "model_used":         "black_scholes",
  "volatility_used": {
    "value":        0.2,
    "source":       "constant",
    "surface_type": "constant"
  },
  "insights": {
    "moneyness":   "out_of_the_money",
    "vol_regime":  "normal"
  }
}
```

---

### POST /v2/options/greeks

Compute delta, gamma, vega, theta, and rho.

**Request** — same fields as `/v2/options/price`, plus:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `method` | `analytic` \| `finite_difference` | `analytic` | `analytic` = closed-form BS; `finite_difference` = bump-and-reprice. Auto-switches to `finite_difference` for non-BS models or matrix vol. |
| `bump_size` | float | `0.01` | Relative bump size for finite-difference |

**Response**

```json
{
  "delta": 0.43,
  "gamma": 0.019,
  "vega":  0.37,
  "theta": -0.017,
  "rho":   0.46,
  "units": {
    "vega":  "per 1% vol change",
    "theta": "per day decay"
  },
  "volatility_used": { "value": 0.2, "source": "constant", "surface_type": "constant" },
  "interpretation": {
    "delta": "Moderate directional exposure",
    "vega":  "Highly sensitive to volatility",
    "theta": "Time decay moderate"
  }
}
```

---

### POST /v2/options/volatility

**Mode 1 — Implied volatility**

Newton-Raphson solver to back out the vol that prices a BS (log-normal) or Bachelier (normal) option to the observed market price.

**Request**

```json
{
  "type":            "implied",
  "option_price":    10.45,
  "option_type":     "call",
  "spot":            100,
  "strike":          100,
  "rate":            0.05,
  "dividend_yield":  0.0,
  "settlement_date": "2026-01-01",
  "expiry_date":     "2027-01-01",
  "day_count":       "ACT/365",
  "vol_type":        "log_normal",
  "initial_guess":   0.2,
  "tolerance":       1e-6,
  "max_iterations":  100
}
```

**Mode 2 — Historical volatility**

Realised vol from a price series, annualised.

```json
{
  "type":                 "historical",
  "prices":               [100, 102, 101, 105, 107],
  "method":               "log_returns",
  "window":               null,
  "annualization_factor": 252
}
```

| Field | Description |
|-------|-------------|
| `method` | `log_returns` (default) or `simple_returns` |
| `window` | Rolling window size; `null` = full series |
| `annualization_factor` | 252 (daily), 52 (weekly), 12 (monthly) |

**Response**

```json
{
  "volatility":          0.2134,
  "type":                "implied",
  "time_to_expiry_days": 365,
  "convergence": {
    "iterations": 4,
    "error":      3.2e-10,
    "status":     "converged"
  },
  "insights": {
    "vol_regime":     "normal",
    "relative_level": "near_historical_avg"
  }
}
```

---

### POST /v2/options/strategies

Analyse a multi-leg option strategy at expiry.

**Request**

```json
{
  "spot":            100,
  "settlement_date": "2026-01-01",
  "legs": [
    { "type": "call", "position": "long",  "strike": 100, "expiry_date": "2027-01-01", "premium": 10 },
    { "type": "call", "position": "short", "strike": 110, "expiry_date": "2027-01-01", "premium": 5  }
  ]
}
```

**Leg fields**

| Field | Type | Description |
|-------|------|-------------|
| `type` | `call` \| `put` | Option right |
| `position` | `long` \| `short` | Bought or sold |
| `strike` | float > 0 | Strike price |
| `expiry_date` | date | Expiry date |
| `premium` | float ≥ 0 | Premium paid (long) or received (short) |

**Auto-identified strategies**

`long_call`, `short_call`, `long_put`, `short_put`, `bull_call_spread`, `bear_call_spread`, `bull_put_spread`, `bear_put_spread`, `long_straddle`, `short_straddle`, `long_strangle`, `short_strangle`, `butterfly_spread`, `reverse_butterfly`, `iron_condor`, `custom`

**Response**

```json
{
  "strategy":   "bull_call_spread",
  "max_profit": 5.0,
  "max_loss":   -5.0,
  "breakevens": [105.0],
  "payoff": [
    { "spot": 80.0,  "value": -5.0 },
    { "spot": 105.0, "value":  0.0 },
    { "spot": 120.0, "value":  5.0 }
  ]
}
```

`max_profit` / `max_loss` are `null` for theoretically unlimited payoffs (e.g. naked long call).

---

## /v2/bonds

### POST /v2/bonds/price

Price a fixed-coupon bond given a yield-to-maturity. Returns dirty price, accrued interest, and clean price.

**Request**

```json
{
  "settlement_date": "2026-01-01",
  "maturity_date":   "2030-01-01",
  "coupon_rate":     0.05,
  "face_value":      1000,
  "frequency":       "semi_annual",
  "ytm":             0.045,
  "day_count":       "30/360"
}
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `settlement_date` | date | ✓ | — | Trade settlement date |
| `maturity_date` | date | ✓ | — | Bond maturity date |
| `coupon_rate` | float ≥ 0 | ✓ | — | Annual coupon rate (e.g. `0.05` = 5%) |
| `face_value` | float > 0 | | `1000` | Par value |
| `frequency` | string | | `semi_annual` | `annual`, `semi_annual`, `quarterly`, `monthly` |
| `ytm` | float | ✓ | — | Yield-to-maturity (e.g. `0.045`) |
| `day_count` | string | | `30/360` | Day count convention |

**Response**

```json
{
  "price":            1025.6,
  "accrued_interest": 12.5,
  "clean_price":      1013.1
}
```

---

### POST /v2/bonds/yield

Solve for the yield-to-maturity that matches an observed clean price.

**Request**

```json
{
  "clean_price":     1013.1,
  "settlement_date": "2026-01-01",
  "maturity_date":   "2030-01-01",
  "coupon_rate":     0.05,
  "face_value":      1000,
  "frequency":       "semi_annual",
  "day_count":       "30/360",
  "initial_guess":   0.05
}
```

**Response**

```json
{
  "ytm":        0.045,
  "iterations": 5,
  "status":     "converged"
}
```

`status` is `"converged"` or `"max_iterations_reached"`.

---

### POST /v2/bonds/sensitivity

Compute Macaulay duration, modified duration, and convexity.

**Request**

```json
{
  "clean_price":     1013.1,
  "settlement_date": "2026-01-01",
  "maturity_date":   "2030-01-01",
  "coupon_rate":     0.05,
  "face_value":      1000,
  "frequency":       "semi_annual",
  "ytm":             0.045,
  "day_count":       "30/360"
}
```

**Response**

```json
{
  "duration":          3.75,
  "modified_duration": 3.6,
  "convexity":         18.2
}
```

| Field | Description |
|-------|-------------|
| `duration` | Macaulay duration — weighted-average time to cash receipt (years) |
| `modified_duration` | Price change per 1-unit (100 bp) parallel yield shift |
| `convexity` | Second-order price sensitivity; improves duration estimate for large moves |

---

## /v2/core

### POST /v2/core/npv

Discount a series of dated cashflows back to a settlement date.

**Request**

```json
{
  "settlement_date": "2026-01-01",
  "cashflows": [
    { "date": "2026-06-01", "amount": 50 },
    { "date": "2027-01-01", "amount": 1050 }
  ],
  "discount_rate": 0.05,
  "day_count":     "ACT/365"
}
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `settlement_date` | date | ✓ | — | Discount origin date |
| `cashflows` | array | ✓ | — | List of `{ date, amount }` objects. All dates must be after `settlement_date`. |
| `discount_rate` | float | ✓ | — | Annual flat discount rate (e.g. `0.05`) |
| `day_count` | string | | `ACT/365` | Day count convention |

**Response**

```json
{
  "npv": 980.25,
  "details": {
    "discount_factors": [0.97561, 0.95181],
    "year_fractions":   [0.41096, 1.00000]
  }
}
```

`details` contains one entry per cashflow in the same order as the request.

---

### POST /v2/core/pmt

Compute the fixed periodic payment for a fully-amortising loan. The number of periods is derived from the dates — no manual period count required.

**Request**

```json
{
  "principal":  100000,
  "rate":       0.08,
  "start_date": "2026-01-01",
  "end_date":   "2031-01-01",
  "frequency":  "monthly"
}
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `principal` | float > 0 | ✓ | — | Loan amount |
| `rate` | float ≥ 0 | ✓ | — | Annual interest rate (e.g. `0.08` = 8%) |
| `start_date` | date | ✓ | — | Loan start date |
| `end_date` | date | ✓ | — | Loan end / final payment date |
| `frequency` | string | | `monthly` | `weekly`, `monthly`, `quarterly`, `semi_annual`, `annual` |

**Response**

```json
{
  "payment":       2027.64,
  "num_periods":   60,
  "total_payment": 121658.4,
  "interest_paid": 21658.4
}
```

---

## /health

### GET /health

> This endpoint is **not** versioned — it is always available at `/health`.

```json
{ "status": "ok", "service": "Voltrix API", "version": "2.0.0" }
```

No authentication required.
