# Research note / 01

**9 October 2026 · deterministic synthetic experiment · local prototype**

## Question

How much protection does a far-contract short provide to a larger near-contract
long, and where does that protection fail?

The demo holds 12 near contracts and shorts 8 far contracts, with assumed multipliers
of 1,000 barrels. A shared random price component creates correlation; the far leg
also carries independent noise. A deliberately injected asymmetric shock tests curve
risk. The 360 weekdays are synthetic observations, not a verified trading calendar.

## Findings reproduced by the demo

A parallel $10 decline loses $40,000: the net exposure is 4,000 barrels. A near-leg
$8 fall accompanied by a far-leg $2 rise loses $112,000: both legs lose money. Thus
a lower net directional exposure does not eliminate curve risk. The negative-price
scenario uses absolute shocks of −$100 and −$60 and loses $720,000 without requiring
log returns or positive-price assumptions.

The final 100-shock historical estimate gives $12,313.13 VaR and $31,857.58 ES at
97.5% confidence. Filtered simulation gives $11,766.25 VaR and $15,062.33 ES.
The methods differ because historical simulation retains the full magnitude of the
injected shock while filtered simulation rescales shocks by conditional volatility
and excludes its initialization sample. Neither result establishes superior accuracy.

Across 259 rolling forecasts, historical and filtered VaR record 12 and 13 exceptions,
respectively, against a nominal expectation of 6.475. This is a descriptive observation
on an artificial path—not evidence that either model is suitable for live risk limits.
The latest $1,719.11 loss reconciles a $5,850.05 near-leg loss with a $4,130.94 far-leg gain.

## Interpretation and next experiment

Tail estimates from short windows are sensitive to very few observations. The final
historical ES averages 2.5 observations of tail mass; filtered ES averages two.
An informative next experiment uses verified settlement histories and tests window,
EWMA decay and confidence sensitivity with independently reconciled contract P&L.

Before operational use, add venue calendars, first-notice controls, quote freshness,
position changes, fees, margin and formal coverage/independence diagnostics. Source
vintages must be aligned to availability before any point-in-time research claim.
The existing platform's dated daily close series is not official settlement evidence.
