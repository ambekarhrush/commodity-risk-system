# Methodology and input contracts

## Accounting

For each contract, exposure is signed integer quantity × positive multiplier.
Variation P&L is exposure × (current price − previous price). Every spread is
represented by its individual legs; position contributions sum to portfolio P&L.
Prices may be zero or negative. All holdings and price units must be USD-compatible;
there is no implicit FX or unit conversion. Gross reference notional sums absolute
price × exposure, and is not futures market value, margin or liquidity.

Holdings are constant throughout the replay. This is a hypothetical current-book
backtest, not a reconstruction of an actual trading account. There is no rolling.
Quotes at or after the supplied last-trade date fail validation. First-notice
exposure and delivery eligibility are not modeled; last-trade validation alone
is not an operational delivery control.

## Risk definitions

Joint absolute price changes retain cross-contract dependence. Positive loss equals
negative P&L. The empirical VaR is the smallest loss whose empirical CDF reaches
confidence alpha (sorted index ceil(alpha × n) − 1). ES integrates exactly the
worst `(1 − alpha) × n` observations, fractionally weighting the boundary observation.
This avoids the tie and noninteger-tail bias of averaging all losses ≥ VaR.
VaR/ES can be negative when all scenarios are profitable; there is no zero floor.

Filtered simulation uses zero-mean EWMA variance with decay 0.94. The first 20
changes initialize mean squared shocks. Each later vector is standardized using
variance **before** that observation; the variance is then updated. Standardized
vectors are jointly rescaled by the final forecast volatility. A 1e-12 variance
floor prevents division by zero. This is an explicit modeling choice, not an
estimated optimal parameter. With a 100-observation window, FHS uses 80 residual
vectors whereas ordinary historical simulation uses all 100 shocks.

For realized change t, forecasts use changes `[t − window, t)` only. An exception
occurs when realized loss strictly exceeds VaR. Expected counts equal number of
forecasts × (1 − alpha). Counts alone are not an independence or coverage test.
ES backtesting and statistical model acceptance are not implemented.

Risk horizons are adjacent supplied observations. Cross-contract missing dates
are rejected, but a date absent from every series cannot be detected without an
exchange calendar. No forward filling or interpolation is performed. Input
snapshots can include later revisions; excluding future price rows is not proof
of historical point-in-time availability.

## Book CSV

One net holding per individual contract:

```csv
contract,quantity,multiplier,currency,unit,expiry
DEMO:ENERGY_NEAR,12,1000,USD,USD/bbl,2027-01-01
DEMO:ENERGY_FAR,-8,1000,USD,USD/bbl,2027-01-01
```

These identities, dates and multipliers are illustrative. Real books require verified
contract specifications. `contract` must match the platform `series` exactly;
`expiry` must agree with dimensions `last_trade_date`.

## Scenario and limit JSON

Scenario shocks are **absolute price-unit changes**, with every held contract explicit:

```json
{"Parallel decline": {"DEMO:ENERGY_NEAR": -10, "DEMO:ENERGY_FAR": -10}}
```

Optional limits are positive USD thresholds; unsupported names are rejected:

```json
{"hs_var": 15000, "hs_es": 20000, "fhs_es": 20000,
 "gross_notional": 1500000, "stress_loss": 75000}
```

Strict threshold exceedance triggers a breach. These values are hypothetical, not
recommendations. `stress_loss` is the largest loss among supplied scenarios, floored
at zero. Worst observed shock replay separately identifies the largest current-book
loss over the entire supplied history. A named real-world historical stress library
has not been validated.

## Shared-platform adapter

Required fields: `source`, `series`, `date`, `value`, `unit`, `frequency`, `kind`,
`dimensions`, `run_id`, `source_sha256`. Only `daily` individual contract closes or
settlements are accepted. Dimensions must encode `exchange`, `contract`, and
`last_trade_date`; `exchange:contract` must agree with `series`. Required fields,
duplicate dates, finite prices, expiry and unit consistency are checked.

The report retains snapshot SHA-256, source run IDs, source hashes and price kinds.
The book/quote exports are also hashed. This preserves traceability, not authenticity
or provider permission. User-supplied positions supply multipliers; the importer
cannot independently verify them from the current platform schema.

## Architecture and verification

`engine.py` contains accounting, risk, scenarios, limits and backtesting. `cli.py`
handles deterministic fixtures, platform ingestion, artifact export and HTML rendering.
No network clients or duplicate data download adapters are introduced.

Tests check independently calculated fractional ES, tied losses, signed spread P&L,
negative price accounting, scale invariance, future-data perturbation, missing quotes,
duplicate keys, unit errors, expiry, platform lineage and strict stress coverage.
A locked environment reproduces artifacts without relying on hosted infrastructure.

For background on expected shortfall and broader market risk requirements, see
[BIS market risk standards](https://www.bis.org/publications/201901-standards-minimum-capital-requirements-market-risk).
This project's one-interval research estimator is not an implementation of that
regulatory framework's calibration, liquidity horizons or capital requirements.
