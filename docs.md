# Voltrix API — Reference

**Version:** 2.0.0
**Base URL:** `/{api_version}` (e.g. `/v2`)
**Interactive UI:** `/docs` (Swagger)



---

## Common Types

### VolatilityInput

Used in `/v2/options/price` and `/v2/options/greeks` as the `volatility` field.
Accepts either a **plain scalar** (e.g. `0.2`, auto-coerced to a constant surface) or a full object:

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
| `vol_type` | `log_normal` \| `normal` \| `cev` | `log_normal` | Vol convention used for scalar-sigma models |
| `surface_type` | `constant` \| `matrix` \| `sabr` \| `svi` \| `heston` | `constant` | How volatility is specified (see below) |
| `data` | object | `{}` | Required for `constant` and `matrix`; not used for parametric surfaces |
| `interpolation` | `bilinear` | `bilinear` | Interpolation method for `matrix` surfaces |
| `extrapolation` | `flat` | `flat` | Behaviour outside surface bounds for `matrix` |
| `other_params` | object | `{}` | Model-specific parameters (see per-surface docs below) |

---

#### surface_type: `"constant"`

A single flat volatility.

```json
{ "surface_type": "constant", "data": { "vol": 0.2 } }
```

Or simply pass a scalar:

```json
"volatility": 0.2
```

---

#### surface_type: `"matrix"`

Bilinear interpolation over a strike × maturity grid. Extrapolation is flat at boundaries.

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
  },
  "interpolation": "bilinear",
  "extrapolation": "flat"
}
```

`vol_matrix[i][j]` is the vol at `strikes[i]` and `maturities[j]` (maturities in year fractions).

---

#### surface_type: `"sabr"`

**SABR** (Hagan et al. 2002). Computes an implied Black-Scholes volatility from the SABR formula
using the current forward `F = S · exp((r−q)·T)`. The resolved implied vol is then used for pricing
with whichever `model` is selected.

```json
{
  "surface_type": "sabr",
  "other_params": {
    "alpha": 0.3,
    "beta":  0.5,
    "rho":   -0.3,
    "nu":    0.4
  }
}
```

| Param | Constraint | Description |
|-------|-----------|-------------|
| `alpha` | > 0 | Initial vol level (σ₀) |
| `beta` | 0 ≤ β ≤ 1 | CEV exponent. `0` = normal; `0.5` = square-root; `1` = log-normal backbone |
| `rho` | −1 < ρ < 1 | Spot-vol Brownian correlation. Negative ρ → downside skew |
| `nu` | ≥ 0 | Vol of vol. `0` = no smile |

SABR requires no `data` field. The `vol_type` setting is ignored (output is always a BS implied vol).

---

#### surface_type: `"svi"`

**SVI** (Gatheral 2004 raw parametrisation). Specifies total implied variance as a function of
log-moneyness `k = ln(K/F)`:

```
w(k) = a + b · (ρ·(k−m) + √((k−m)² + σ²))
```

Implied vol is recovered as `σ_impl = √(w/T)`.

```json
{
  "surface_type": "svi",
  "other_params": {
    "a":     0.04,
    "b":     0.2,
    "rho":   -0.3,
    "m":     0.0,
    "sigma": 0.3
  }
}
```

| Param | Constraint | Description |
|-------|-----------|-------------|
| `a` | — | Vertical translation (overall level of total variance) |
| `b` | ≥ 0 | Angle / breadth; controls smile wings |
| `rho` | −1 < ρ < 1 | Asymmetry / skew |
| `m` | — | ATM shift in log-moneyness space |
| `sigma` | > 0 | Minimum smile width / curvature |

Parameters must satisfy `a + b·σ·√(1−ρ²) ≥ 0` (butterfly arbitrage-free condition). The API
returns a 400 error if the resolved total variance `w ≤ 0`.

---

#### surface_type: `"heston"`

**Heston (1993) stochastic-vol model.** Used together with `model: "heston"` for pricing.
Must supply all five model parameters in `other_params`:

```json
{
  "surface_type": "heston",
  "other_params": {
    "v0":      0.04,
    "kappa":   2.0,
    "theta":   0.04,
    "sigma_v": 0.3,
    "rho":     -0.7
  }
}
```

| Param | Constraint | Description |
|-------|-----------|-------------|
| `v0` | > 0 | Initial variance. Initial vol ≈ √v₀ (e.g. `0.04` → 20% vol) |
| `kappa` | > 0 | Mean-reversion speed of variance |
| `theta` | > 0 | Long-run variance (long-run vol ≈ √θ) |
| `sigma_v` | > 0 | Volatility of variance ("vol of vol") |
| `rho` | −1 < ρ < 1 | Spot-variance correlation. Negative → left skew |

**Feller condition** `2·κ·θ > σᵥ²` ensures variance stays positive; the API does not enforce this
but instability may occur if it is badly violated.

**Optional:** add `"use_mc": true` to `other_params` to use Monte Carlo pricing instead of the
default semi-analytic characteristic-function method.

The `volatility_used.value` in the response reports `√v₀` as a reference implied-vol level.

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

| `model` | Method | Description |
|---------|--------|-------------|
| `black_scholes` | Analytic | Black-Scholes-Merton (log-normal); default |
| `bachelier` | Analytic | Bachelier normal model |
| `cev` | Monte Carlo | CEV `dS = (r−q)S dt + σ Sᵝ dW`; set `cev_beta` in `other_params` |
| `monte_carlo` | Monte Carlo | Risk-neutral GBM simulation |
| `heston` | Semi-analytic / MC | Heston stochastic-vol; requires `surface_type: "heston"` |

`black_scholes`, `bachelier`, `cev`, and `monte_carlo` accept any `surface_type` for vol resolution —
SABR/SVI/matrix implied vols are resolved to a scalar first, then passed to the chosen model.

`heston` uses its own characteristic-function pricer and ignores the resolved scalar vol.

**Request**

```json
{
  "model":            "black_scholes",
  "option_type":      "call",
  "spot":             100,
  "strike":           105,
  "rate":             0.05,
  "dividend_yield":   0.0,
  "settlement_date":  "2026-04-01",
  "expiry_date":      "2027-04-01",
  "day_count":        "ACT/365",
  "volatility":       0.2,
  "num_simulations":  10000,
  "seed":             null,
  "include_insights": false
}
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `model` | string | | `black_scholes` | Pricing model |
| `option_type` | `call` \| `put` | | `call` | Option right |
| `spot` | float > 0 | ✓ | — | Current underlying price |
| `strike` | float > 0 | ✓ | — | Strike price |
| `rate` | float | ✓ | — | Continuously compounded risk-free rate (e.g. `0.05`) |
| `dividend_yield` | float | | `0.0` | Continuous dividend yield |
| `settlement_date` | date | ✓ | — | Valuation date (`YYYY-MM-DD`) |
| `expiry_date` | date | ✓ | — | Expiry date (`YYYY-MM-DD`) |
| `day_count` | string | | `ACT/365` | Day count convention |
| `volatility` | float \| VolatilityInput | ✓ | — | Scalar or vol surface object |
| `num_simulations` | int | | `10000` | MC paths (MC-based models only) |
| `seed` | int \| null | | `null` | RNG seed for reproducible MC |
| `include_insights` | bool | | `false` | Add plain-language interpretation |

**Response**

```json
{
  "price":               8.73,
  "time_to_expiry_days": 365,
  "model_used":          "black_scholes",
  "volatility_used": {
    "value":        0.2,
    "source":       "constant",
    "surface_type": "constant"
  },
  "insights": {
    "moneyness":  "out_of_the_money",
    "vol_regime": "normal"
  }
}
```

`volatility_used.source` is `"constant"`, `"interpolated"`, `"sabr"`, `"svi"`, or `"heston"`.

---

#### Example — SABR surface with Black-Scholes pricing

```json
{
  "model":           "black_scholes",
  "option_type":     "call",
  "spot":            100,
  "strike":          105,
  "rate":            0.05,
  "settlement_date": "2026-04-01",
  "expiry_date":     "2027-04-01",
  "volatility": {
    "surface_type": "sabr",
    "other_params": { "alpha": 0.3, "beta": 0.5, "rho": -0.3, "nu": 0.4 }
  }
}
```

The SABR formula resolves an implied BS vol for the given (K, T, F) and prices via Black-Scholes.

---

#### Example — SVI surface with Black-Scholes pricing

```json
{
  "model":           "black_scholes",
  "option_type":     "put",
  "spot":            100,
  "strike":          95,
  "rate":            0.05,
  "settlement_date": "2026-04-01",
  "expiry_date":     "2027-04-01",
  "volatility": {
    "surface_type": "svi",
    "other_params": { "a": 0.04, "b": 0.2, "rho": -0.3, "m": 0.0, "sigma": 0.3 }
  }
}
```

---

#### Example — Heston semi-analytic pricing

```json
{
  "model":           "heston",
  "option_type":     "call",
  "spot":            100,
  "strike":          105,
  "rate":            0.05,
  "settlement_date": "2026-04-01",
  "expiry_date":     "2027-04-01",
  "volatility": {
    "surface_type": "heston",
    "other_params": {
      "v0": 0.04, "kappa": 2.0, "theta": 0.04, "sigma_v": 0.3, "rho": -0.7
    }
  }
}
```

---

#### Example — Heston Monte Carlo pricing

Add `"use_mc": true` to `other_params` to switch from the semi-analytic integrator to a
full-truncation Euler-Maruyama simulation. Useful as a cross-check or when parameters
are near the boundary of numerical stability.

```json
{
  "model":            "heston",
  "option_type":      "call",
  "spot":             100,
  "strike":           105,
  "rate":             0.05,
  "settlement_date":  "2026-04-01",
  "expiry_date":      "2027-04-01",
  "num_simulations":  100000,
  "seed":             42,
  "volatility": {
    "surface_type": "heston",
    "other_params": {
      "v0": 0.04, "kappa": 2.0, "theta": 0.04, "sigma_v": 0.3,
      "rho": -0.7, "use_mc": true
    }
  }
}
```

---

### POST /v2/options/greeks

Compute delta, gamma, vega, theta, and rho.

**Automatic method selection**

| Condition | Method forced |
|-----------|--------------|
| `model = "black_scholes"` and `surface_type = "constant"` or `"matrix"` with `method = "analytic"` | Analytic (closed-form) |
| `model ≠ "black_scholes"` | `finite_difference` |
| `surface_type` is `"matrix"`, `"sabr"`, `"svi"`, or `"heston"` | `finite_difference` |

**Vega definition by model**

| Model | Vega measures |
|-------|--------------|
| `black_scholes`, `bachelier`, `cev`, `monte_carlo` | ∂P/∂σ per 1% absolute vol change |
| `heston` | ∂P/∂σ₀ per 1% change in σ₀ = √v₀ (initial vol) |

**Request** — same fields as `/v2/options/price`, plus:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `method` | `analytic` \| `finite_difference` | `analytic` | Greeks method; auto-overridden (see table above) |
| `bump_size` | float | `0.01` | Relative bump for finite-difference (e.g. `0.01` = 1%) |

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

#### Example — Heston Greeks

```json
{
  "model":           "heston",
  "option_type":     "call",
  "spot":            100,
  "strike":          105,
  "rate":            0.05,
  "settlement_date": "2026-04-01",
  "expiry_date":     "2027-04-01",
  "volatility": {
    "surface_type": "heston",
    "other_params": {
      "v0": 0.04, "kappa": 2.0, "theta": 0.04, "sigma_v": 0.3, "rho": -0.7
    }
  }
}
```

Greeks are always computed via finite-difference for Heston; `"method": "analytic"` is silently
overridden. Vega reports ∂price/∂σ₀ (per 1% change in initial vol √v₀).

---

#### Example — SABR Greeks

```json
{
  "model":           "black_scholes",
  "option_type":     "call",
  "spot":            100,
  "strike":          105,
  "rate":            0.05,
  "settlement_date": "2026-04-01",
  "expiry_date":     "2027-04-01",
  "volatility": {
    "surface_type": "sabr",
    "other_params": { "alpha": 0.3, "beta": 0.5, "rho": -0.3, "nu": 0.4 }
  }
}
```

Delta and vega correctly account for the SABR smile shape through bump-and-reprice.

---

### POST /v2/options/volatility

Three operating modes selected by `type` and `vol_type`.

---

#### Mode 1 — Back-solve implied vol (`type: "implied"`, `vol_type: "log_normal"` or `"normal"`)

Newton-Raphson solver that finds the vol making the model price equal the observed market price.

| `vol_type` | Pricing model used for inversion |
|------------|----------------------------------|
| `log_normal` | Black-Scholes (default) |
| `normal` | Bachelier |

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
  "settlement_date": "2026-04-01",
  "expiry_date":     "2027-04-01",
  "day_count":       "ACT/365",
  "vol_type":        "log_normal",
  "initial_guess":   0.2,
  "tolerance":       1e-6,
  "max_iterations":  100
}
```

---

#### Mode 2 — Evaluate parametric model vol (`type: "implied"`, `vol_type: "sabr"|"svi"|"heston"|"cev"`)

Evaluates the model's implied vol analytically at the given (K, T) without back-solving.
No `option_price` required. Pass calibrated parameters (from `/options/calibration/*`) via `model_params`.

| `vol_type` | Required `model_params` keys | Formula |
|------------|------------------------------|---------|
| `sabr` | `alpha`, `beta`, `rho`, `nu` | Hagan et al. (2002) SABR |
| `svi` | `a`, `b`, `rho`, `m`, `sigma` | Gatheral raw SVI |
| `heston` | `v0`, `kappa`, `theta`, `sigma_v`, `rho` | Returns `√v₀` as reference vol |
| `cev` | `sigma`, `beta` | Hagan-Woodward CEV-to-BS approximation |

**Request — SABR example**

```json
{
  "type":            "implied",
  "vol_type":        "sabr",
  "spot":            100,
  "strike":          105,
  "rate":            0.05,
  "dividend_yield":  0.0,
  "settlement_date": "2026-04-01",
  "expiry_date":     "2027-04-01",
  "model_params": {
    "alpha": 0.3,
    "beta":  0.5,
    "rho":   -0.4,
    "nu":    0.6
  }
}
```

**Request — SVI example**

```json
{
  "type":       "implied",
  "vol_type":   "svi",
  "spot":       100,
  "strike":     95,
  "rate":       0.05,
  "settlement_date": "2026-04-01",
  "expiry_date":     "2027-04-01",
  "model_params": { "a": 0.01, "b": 0.12, "rho": -0.5, "m": 0.0, "sigma": 0.15 }
}
```

---

#### Mode 3 — Historical volatility (`type: "historical"`)

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

---

**Response**

```json
{
  "volatility":          0.2134,
  "type":                "implied",
  "vol_model":           "log_normal",
  "time_to_expiry_days": 365,
  "convergence": {
    "iterations": 4,
    "error":      3.2e-10,
    "status":     "converged"
  },
  "insights": { "vol_regime": "normal" }
}
```

| Field | Values | Description |
|-------|--------|-------------|
| `type` | `implied`, `model`, `historical` | `model` when a parametric vol_type was used |
| `vol_model` | `log_normal`, `normal`, `sabr`, `svi`, `heston`, `cev` | Vol model used |
| `convergence` | object or `null` | Present only for `type=implied` (back-solver modes) |

---

### POST /v2/options/strategies

Analyse a multi-leg option strategy at expiry.

**Request**

```json
{
  "spot":            100,
  "settlement_date": "2026-04-01",
  "legs": [
    { "type": "call", "position": "long",  "strike": 100, "expiry_date": "2027-04-01", "premium": 10 },
    { "type": "call", "position": "short", "strike": 110, "expiry_date": "2027-04-01", "premium": 5  }
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

`long_call`, `short_call`, `long_put`, `short_put`, `bull_call_spread`, `bear_call_spread`,
`bull_put_spread`, `bear_put_spread`, `long_straddle`, `short_straddle`, `long_strangle`,
`short_strangle`, `butterfly_spread`, `reverse_butterfly`, `iron_condor`, `custom`

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

## /v2/options/calibration

Fit volatility model parameters to a set of observed market option prices.
All calibration endpoints share the same request base:

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `observations` | array | ✓ | — | List of market option observations (see below) |
| `spot` | float > 0 | ✓ | — | Current underlying spot price |
| `rate` | float | ✓ | — | Continuously compounded risk-free rate |
| `dividend_yield` | float | | `0.0` | Continuous dividend yield |
| `settlement_date` | date | ✓ | — | Valuation / trade date |
| `day_count` | string | | `ACT/365` | Day count convention |

Each observation in `observations`:

| Field | Type | Description |
|-------|------|-------------|
| `option_type` | `call` \| `put` | Option right |
| `strike` | float > 0 | Strike price |
| `expiry_date` | date | Option expiry date (must be after `settlement_date`) |
| `market_price` | float > 0 | Observed market option price |

Calibrated parameters can be used directly in any `/options/*` endpoint — pass them as
`volatility.other_params` with the matching `surface_type`, or as `model_params` in
`/options/volatility`.

---

### POST /v2/options/calibration/sabr

Fit Hagan et al. (2002) SABR parameters **(α, ρ, ν)** with **β fixed**.

**Algorithm:** Back-solves market prices to Black-Scholes implied vols, then minimises sum of
squared (SABR vol − market vol)² with L-BFGS-B using multiple restarts.

**Minimum observations:** 3 options with distinct strikes.

**Additional field**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `beta` | float 0–1 | `0.5` | CEV exponent (fixed). `0`=normal, `0.5`=square-root, `1`=log-normal |

**Request**

```json
{
  "spot": 100, "rate": 0.05, "settlement_date": "2026-04-01", "day_count": "ACT/365",
  "beta": 0.5,
  "observations": [
    { "option_type": "call", "strike": 90,  "expiry_date": "2027-04-01", "market_price": 12.5 },
    { "option_type": "call", "strike": 95,  "expiry_date": "2027-04-01", "market_price": 9.2  },
    { "option_type": "call", "strike": 100, "expiry_date": "2027-04-01", "market_price": 6.5  },
    { "option_type": "call", "strike": 105, "expiry_date": "2027-04-01", "market_price": 4.3  },
    { "option_type": "call", "strike": 110, "expiry_date": "2027-04-01", "market_price": 2.7  }
  ]
}
```

**Response**

```json
{
  "alpha":          0.3001,
  "beta":           0.5,
  "rho":           -0.3998,
  "nu":             0.5999,
  "rmse":           0.000002,
  "n_observations": 5,
  "converged":      true,
  "message":        "CONVERGENCE: NORM_OF_PROJECTED_GRADIENT_<=_PGTOL"
}
```

| Field | Description |
|-------|-------------|
| `alpha` | Calibrated initial vol level α > 0 |
| `beta` | CEV exponent (echoed from input) |
| `rho` | Calibrated spot-vol correlation ρ ∈ (−1, 1) |
| `nu` | Calibrated vol-of-vol ν ≥ 0 |
| `rmse` | Root-mean-square error in implied vol units |
| `n_observations` | Observations that produced valid implied vols |
| `converged` | Whether the optimizer reported convergence |

**Using the result in `/options/price`:**

```json
{
  "model": "black_scholes",
  "volatility": {
    "surface_type": "sabr",
    "other_params": { "alpha": 0.3001, "beta": 0.5, "rho": -0.3998, "nu": 0.5999 }
  }
}
```

---

### POST /v2/options/calibration/svi

Fit Gatheral (2004) raw SVI parameters **(a, b, ρ, m, σ)**.

**Algorithm:** Back-solves to implied vols, minimises squared SVI-vs-market vol errors with the
butterfly-arbitrage-free constraint `a + b·σ·√(1−ρ²) ≥ 0` enforced.

**Minimum observations:** 4 options with distinct strikes.

**Request** — same base as SABR, no extra fields.

**Response**

```json
{
  "a":              0.0100,
  "b":              0.1200,
  "rho":           -0.5000,
  "m":              0.0000,
  "sigma":          0.1500,
  "rmse":           0.000015,
  "n_observations": 8,
  "converged":      true,
  "message":        "CONVERGENCE: NORM_OF_PROJECTED_GRADIENT_<=_PGTOL"
}
```

**Using the result in `/options/price`:**

```json
{
  "model": "black_scholes",
  "volatility": {
    "surface_type": "svi",
    "other_params": { "a": 0.01, "b": 0.12, "rho": -0.5, "m": 0.0, "sigma": 0.15 }
  }
}
```

---

### POST /v2/options/calibration/heston

Fit Heston (1993) model parameters **(v₀, κ, θ, σᵥ, ρ)** directly to option prices.

**Algorithm:** Differential evolution for global search, then L-BFGS-B refinement. The
semi-analytic characteristic-function pricer is used throughout — no Monte Carlo.

**Minimum observations:** 5 options (ideally spanning multiple strikes and maturities).

**Response**

```json
{
  "v0":                          0.0401,
  "kappa":                       1.998,
  "theta":                       0.0400,
  "sigma_v":                     0.301,
  "rho":                        -0.699,
  "rmse":                        0.012,
  "n_observations":              7,
  "converged":                   true,
  "feller_condition_satisfied":  true,
  "message":                     "CONVERGENCE: NORM_OF_PROJECTED_GRADIENT_<=_PGTOL"
}
```

| Field | Description |
|-------|-------------|
| `rmse` | Root-mean-square error in **price** units |
| `feller_condition_satisfied` | `2κθ > σᵥ²`: variance stays positive almost surely |

**Using the result in `/options/price`:**

```json
{
  "model": "heston",
  "volatility": {
    "surface_type": "heston",
    "other_params": { "v0": 0.0401, "kappa": 1.998, "theta": 0.04, "sigma_v": 0.301, "rho": -0.699 }
  }
}
```

---

### POST /v2/options/calibration/cev

Fit CEV model parameters **(σ, β)** using the Hagan-Woodward (1999) analytic vol approximation.
Avoids slow Monte Carlo entirely during calibration.

**Minimum observations:** 2 options with distinct strikes.

**β interpretation:** `β=1` → log-normal (Black-Scholes), `β=0.5` → square-root, `β=0` → normal.

**Response**

```json
{
  "sigma":          0.2980,
  "beta":           0.502,
  "rmse":           0.000008,
  "n_observations": 5,
  "converged":      true,
  "message":        "CONVERGENCE: NORM_OF_PROJECTED_GRADIENT_<=_PGTOL"
}
```

**Using the result in `/options/price`:**

```json
{
  "model": "cev",
  "volatility": {
    "surface_type": "constant",
    "data": { "vol": 0.298 },
    "other_params": { "cev_beta": 0.502 }
  }
}
```

**Error Responses**

| HTTP | Code | Cause |
|------|------|-------|
| 400 | `CALIBRATION_ERROR` | Insufficient valid observations after implied-vol extraction |
| 422 | `INVALID_INPUT` | `expiry_date` before `settlement_date`, or missing required fields |

---

## /v2/bonds

### POST /v2/bonds/price

Price a fixed-coupon bond given a yield-to-maturity. Returns dirty price, accrued interest, and clean price.

**Request**

```json
{
  "settlement_date": "2026-04-01",
  "maturity_date":   "2030-04-01",
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
  "settlement_date": "2026-04-01",
  "maturity_date":   "2030-04-01",
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
  "settlement_date": "2026-04-01",
  "maturity_date":   "2030-04-01",
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
  "settlement_date": "2026-04-01",
  "cashflows": [
    { "date": "2026-10-01", "amount": 50 },
    { "date": "2027-04-01", "amount": 1050 }
  ],
  "discount_rate": 0.05,
  "day_count":     "ACT/365"
}
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `settlement_date` | date | ✓ | — | Discount origin date |
| `cashflows` | array | ✓ | — | List of `{ date, amount }`. All dates must be after `settlement_date`. |
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

Compute the fixed periodic payment for a fully-amortising loan. The number of periods is derived
from the dates — no manual period count required.

**Request**

```json
{
  "principal":  100000,
  "rate":       0.08,
  "start_date": "2026-04-01",
  "end_date":   "2031-04-01",
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

---

## Volatility Model Quick Reference

### Choosing a vol surface

| Use case | `surface_type` | Required `other_params` |
|----------|---------------|------------------------|
| Single flat vol | `constant` | — (`data.vol`) |
| Market vol grid | `matrix` | — (`data.strikes/maturities/vol_matrix`) |
| Parametric smile (calibrated) | `sabr` | `alpha`, `beta`, `rho`, `nu` |
| Total-variance smile | `svi` | `a`, `b`, `rho`, `m`, `sigma` |
| Stochastic-vol model | `heston` | `v0`, `kappa`, `theta`, `sigma_v`, `rho` |

### Choosing a pricing model

| `model` | Vol surface compatibility | Greeks method |
|---------|--------------------------|--------------|
| `black_scholes` | All surface types | Analytic (constant) or FD (others) |
| `bachelier` | `constant`, `matrix`, `sabr`, `svi` | Finite-difference |
| `cev` | `constant`, `matrix`, `sabr`, `svi` | Finite-difference |
| `monte_carlo` | `constant`, `matrix`, `sabr`, `svi` | Finite-difference |
| `heston` | `heston` only | Finite-difference (bumps v₀) |

### Calibration → Usage Mapping

| Calibration endpoint | Calibrates | Use in pricing / vol eval |
|---------------------|------------|--------------------------|
| `/calibration/sabr` | α, β (fixed), ρ, ν | `volatility.surface_type = "sabr"` |
| `/calibration/svi` | a, b, ρ, m, σ | `volatility.surface_type = "svi"` |
| `/calibration/heston` | v₀, κ, θ, σᵥ, ρ | `model = "heston"`, `volatility.surface_type = "heston"` |
| `/calibration/cev` | σ, β | `model = "cev"`, `volatility.other_params.cev_beta = β` |

### Typical workflow

```
1. Observe market option prices across strikes / maturities
2. POST /v2/options/calibration/{model}  → get calibrated parameters + RMSE
3. POST /v2/options/volatility (vol_type = model)
       with model_params = calibrated params  → evaluate smile at any (K, T)
4. POST /v2/options/price / /options/greeks
       with volatility.surface_type = model  → price / risk with calibrated surface
```

### Heston parameter guidance

| Regime | Typical values |
|--------|---------------|
| Equity (S&P-like) | v0=0.04, κ=2, θ=0.04, σᵥ=0.3–0.6, ρ=−0.7 to −0.5 |
| Low-vol | v0=0.01, κ=3, θ=0.01, σᵥ=0.2, ρ=−0.5 |
| High-vol | v0=0.09, κ=1, θ=0.09, σᵥ=0.5, ρ=−0.8 |

Use `heston` MC (`"use_mc": true`) with a large `num_simulations` (50 000+) as a cross-check of
the semi-analytic result. Both should agree within a few basis points.

### SABR parameter guidance

| β value | Backbone | Typical α range | Use case |
|---------|----------|-----------------|----------|
| `0.0` | Normal (flat backbone) | 0.05–0.15 | Interest rate options |
| `0.5` | Square-root (CIR-like) | 0.1–0.5 | General equity / commodity |
| `1.0` | Log-normal | 0.1–0.5 | Equivalent to Black-Scholes backbone |

ρ < 0 produces left skew (equity-like); ρ > 0 right skew (commodity-like). ν controls smile curvature.

### SVI arbitrage conditions

The raw SVI parametrisation `w(k) = a + b·(ρ·(k−m) + √((k−m)²+σ²))` is free of butterfly
arbitrage when `a + b·σ·√(1−ρ²) ≥ 0`. Calendar-spread arbitrage requires additional checks
across maturities that are not automatically enforced.


---

## Performance Benchmarks

Average response times measured at the core computation layer (excludes HTTP overhead).

### Options Pricing

| Endpoint | Avg |
|---|---|
| Black-Scholes (call/put) | 0.05 ms |
| Bachelier | 0.06 ms |
| Monte Carlo GBM (10k paths) | 0.12 ms |
| Monte Carlo GBM (100k paths) | 1.21 ms |
| CEV (beta=0.5, 10k MC paths) | 29 ms |
| Heston semi-analytic | 3.2 ms |
| Heston MC (10k paths) | 67 ms |

### Greeks

| Endpoint | Avg |
|---|---|
| Black-Scholes analytic | 0.18 ms |
| Black-Scholes finite-difference | 0.39 ms |
| Monte Carlo numerical (10k paths) | 1.0 ms |
| Heston numerical (semi-analytic) | 22 ms |
| CEV numerical (10k MC paths) | 234 ms |

### Volatility

| Endpoint | Avg |
|---|---|
| Implied vol (BS log-normal) | 0.20 ms |
| SABR implied vol | < 0.01 ms |
| SVI implied vol | < 0.01 ms |
| Vol surface resolve (constant) | < 0.01 ms |
| Vol surface resolve (matrix interp) | 0.04 ms |
| Vol surface resolve (SABR) | < 0.01 ms |

### Strategies

| Endpoint | Avg |
|---|---|
| Bull call spread (2 legs) | 0.05 ms |
| Iron condor (4 legs) | 0.06 ms |
| Butterfly (4 legs) | 0.07 ms |

### Bonds

| Endpoint | Avg |
|---|---|
| Bond price (5yr semi-annual) | 0.02 ms |
| Bond price (30yr semi-annual) | 0.12 ms |
| Yield solve (5yr) | 0.04 ms |
| Yield solve (10yr) | 0.06 ms |
| Yield solve (30yr) | 0.14 ms |
| Duration/convexity (5yr) | 0.02 ms |
| Duration/convexity (30yr) | 0.08 ms |

### Core Finance

| Endpoint | Avg |
|---|---|
| NPV (5 cashflows) | 0.01 ms |
| NPV (60 cashflows) | 0.05 ms |
| PMT (monthly, 30yr) | < 0.01 ms |

### Calibration

| Endpoint | 7 obs | 20 obs |
|---|---|---|
| SABR | 22 ms | 29 ms |
| SVI | 11 ms | 8 ms |
| CEV | 59 ms | 47 ms |
| Heston | 7.5 s | 8.8 s |

Heston calibration uses differential evolution (global optimizer) with vectorized Gauss-Legendre quadrature pricing. All other calibrators use vectorized NumPy loss functions with L-BFGS-B.