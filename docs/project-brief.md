# Commodity Risk System

*Synthetic futures and spread-book demonstration · Prepared 5 November 2026*

## The research question

What does a futures book lose, and can each risk figure be reconciled to holdings and shocks?

## Approach

Explicit contract holdings drive variation P&L, joint historical simulation, EWMA filtered risk, scenarios, limits and rolling exception forecasts. The platform importer checks individual-contract metadata and rejects unsupported price proxies.

## Evidence and result

The seeded demonstration uses 360 synthetic observations and produces 259 forecasts. Saved results show historical VaR/ES of $12,313.13 / $31,857.58 and 12 historical VaR exceptions. The fresh local suite passes 16 tests.

## Scope and limitations

An injected curve shock is intentional. These are accounting demonstrations, not observed commodity returns or risk calibration. Authorized settlement histories, position changes, expiry handling and independent system validation are outstanding.

## Explore the project

Run uv run commodity-risk demo and inspect the self-contained HTML, JSON and forecast audit. No keys or sibling repository are needed for the synthetic route.

## Sources and evidence

[examples/demo-report.json](../examples/demo-report.json) · [docs/RESEARCH.md](../docs/RESEARCH.md) · [docs/METHODOLOGY.md](../docs/METHODOLOGY.md)

---

Hrush Ambekar · Research snapshot reviewed 5 November 2026. See linked source files for full methodology, figures and reproducibility.
