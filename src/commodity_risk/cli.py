"""Offline demonstration and shared-platform snapshot ingestion."""

import argparse
import hashlib
import html
import json
from pathlib import Path

import numpy as np
import pandas as pd

from commodity_risk.engine import analyze


def platform_quotes(path: Path, book: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    frame = pd.read_parquet(path)
    required = {
        "source",
        "series",
        "date",
        "value",
        "unit",
        "frequency",
        "kind",
        "dimensions",
        "run_id",
        "source_sha256",
    }
    if not required.issubset(frame):
        raise ValueError("Expected versioned commodity-data-platform Parquet schema")
    selected = frame[frame.series.isin(book.contract)].copy()
    if selected.empty or selected[list(required)].isna().any().any():
        raise ValueError("Missing versioned futures observations")
    if not set(selected.kind).issubset({"futures_contract_close", "futures_contract_settlement"}):
        raise ValueError("Only individual futures contracts are supported; no spot/rank proxies")
    if set(selected.frequency) != {"daily"}:
        raise ValueError("Daily contract observations required")
    for row in selected.itertuples():
        dimensions = json.loads(str(row.dimensions))
        if f"{dimensions['exchange']}:{dimensions['contract']}" != row.series:
            raise ValueError("Contract identity mismatch")
        expiry = book.set_index("contract").loc[str(row.series), "expiry"]
        if pd.Timestamp(dimensions["last_trade_date"]) != pd.Timestamp(str(expiry)):
            raise ValueError("Book expiry disagrees with source metadata")
    quotes = selected.rename(columns={"series": "contract", "value": "price"})
    provenance = {
        "mode": "platform snapshot — research only",
        "snapshot_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "run_ids": sorted(selected.run_id.unique().tolist()),
        "source_sha256": sorted(selected.source_sha256.unique().tolist()),
        "price_kinds": sorted(selected.kind.unique().tolist()),
    }
    return quotes, provenance


def demo() -> tuple[pd.DataFrame, pd.DataFrame, dict, dict]:
    rng = np.random.default_rng(20261009)
    dates = pd.bdate_range("2025-01-02", periods=360)
    common = rng.normal(0, 0.9, len(dates))
    shocks = np.column_stack([common, 0.88 * common + rng.normal(0, 0.3, len(dates))])
    shocks[270] = [-9, -6]
    prices = np.array([72.0, 74.0]) + shocks.cumsum(axis=0)
    contracts = ["DEMO:ENERGY_NEAR", "DEMO:ENERGY_FAR"]
    quotes = pd.DataFrame(
        [
            {"date": date, "contract": c, "price": prices[i, j], "unit": "USD/bbl"}
            for i, date in enumerate(dates)
            for j, c in enumerate(contracts)
        ]
    )
    book = pd.DataFrame(
        {
            "contract": contracts,
            "quantity": [12, -8],
            "multiplier": [1000.0, 1000.0],
            "currency": ["USD", "USD"],
            "unit": ["USD/bbl", "USD/bbl"],
            "expiry": ["2027-01-01"] * 2,
        }
    )
    scenarios = {
        "Parallel decline / hypothetical": dict(zip(contracts, [-10.0, -10.0])),
        "Curve inversion / hypothetical": dict(zip(contracts, [-8.0, 2.0])),
        "Negative price / hypothetical": dict(zip(contracts, [-100.0, -60.0])),
    }
    provenance = {
        "mode": "SYNTHETIC DEMONSTRATION",
        "seed": 20261009,
        "price_kinds": ["synthetic"],
        "calendar": "weekdays; not an exchange calendar",
    }
    return quotes, book, scenarios, provenance


def render(report: dict, book: pd.DataFrame) -> str:
    esc = html.escape

    def money(value: float) -> str:
        return f"{'−' if value < 0 else ''}${abs(value):,.0f}"

    def table(headers: list[str], rows: list[list[str]]) -> str:
        return (
            "<table><thead><tr>"
            + "".join(f"<th>{esc(x)}</th>" for x in headers)
            + "</tr></thead><tbody>"
            + "".join("<tr>" + "".join(f"<td>{esc(x)}</td>" for x in row) + "</tr>" for row in rows)
            + "</tbody></table>"
        )

    cards = [
        ("Daily variation P&L", report["daily_pnl"]),
        ("Historical VaR", report["hs"]["var"]),
        ("Historical ES", report["hs"]["es"]),
        ("Filtered ES", report["fhs"]["es"]),
    ]
    holdings = table(
        ["Position / synthetic in demo", "Contracts", "Daily P&L"],
        [
            [
                str(r.contract),
                f"{int(float(str(r.quantity))):+d}",
                money(report["contributions"][r.contract]),
            ]
            for r in book.itertuples()
        ],
    )
    stress = table(
        ["Scenario • absolute price shocks", "P&L"],
        [[k, money(v)] for k, v in report["stresses"].items()],
    )
    limits = table(
        ["Limit", "Observed", "Threshold", "Result"],
        [
            [
                r["measure"].replace("_", " ").title(),
                money(r["value"]),
                money(r["limit"]),
                "BREACH" if r["breach"] else "Within",
            ]
            for r in report["limits"]
        ],
    )
    bt = report["backtest"]
    return f"""<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Commodity Risk / Brief</title>
<style>
:root{{color-scheme:light;font-family:Arial,sans-serif;color:#152a34;background:#e9efef}}
*{{box-sizing:border-box}}body{{max-width:1120px;margin:32px auto;padding:40px;background:#fff}}
header{{border-top:5px solid #18796e;padding-top:20px}}.eyebrow{{letter-spacing:2px;font-size:11px;font-weight:700;color:#16675e}}
h1{{font-size:44px;letter-spacing:-2px;margin:12px 0}}.sub,footer{{color:#4f626b;font-size:13px;line-height:1.6}}
.badge{{display:inline-block;background:#f6e9c9;color:#63460a;padding:8px 12px;font-size:11px;font-weight:bold}}
.cards{{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:28px 0}}
.card{{padding:18px;background:#edf5f3;border-top:2px solid #18796e}}.card span{{font-size:11px}}.card strong{{display:block;font-size:28px;margin-top:9px}}
h2{{font-size:16px;margin:22px 0 12px}}.grid{{display:grid;grid-template-columns:1fr 1fr;gap:28px}}
table{{width:100%;border-collapse:collapse;font-size:12px}}th{{text-align:left;color:#4f626b;font-size:10px}}td,th{{padding:10px 5px;border-bottom:1px solid #dce5e5}}td:not(:first-child),th:not(:first-child){{text-align:right}}
.note{{background:#f4f6f7;padding:14px;font-size:12px;line-height:1.6}}footer{{border-top:1px solid #cedada;margin-top:24px;padding-top:12px;font-size:11px}}
@media(max-width:700px){{body{{margin:0;padding:20px}}h1{{font-size:34px}}.cards{{grid-template-columns:1fr 1fr}}.grid{{grid-template-columns:1fr}}}}
@media print{{@page{{size:A4 landscape;margin:12mm}}body{{margin:0;padding:0;max-width:none}}h1{{font-size:32px}}.cards{{margin:16px 0}}td,th{{padding:7px 4px}}footer{{margin-top:12px}}}}
</style><header><div class="eyebrow">COMMODITY RESEARCH / 02 — RISK SYSTEM</div>
<h1>The book, under stress.</h1><span class="badge">{esc(report["provenance"]["mode"])}</span>
<p class="sub">As of {report["as_of"]} · USD · {report["confidence"]:.1%} confidence · {report["window"]} observed intervals · Fixed holdings</p></header>
<div class="cards">{"".join(f'<div class="card"><span>{label}</span><strong>{money(value)}</strong></div>' for label, value in cards)}</div>
<div class="grid"><section><h2>01 / Position reconciliation</h2>{holdings}
<p class="sub">Gross reference notional {money(report["gross_notional"])}. This is not futures market value.</p>
<h2>02 / Scenario losses</h2>{stress}</section>
<section><h2>03 / Illustrative risk limits</h2>{limits}<h2>04 / Rolling forecast audit</h2>
<div class="note">{bt["observations"]} out-of-sample forecasts · {bt["hs_exceptions"]} historical VaR exceptions · {bt["fhs_exceptions"]} filtered VaR exceptions.<br>
Nominal expected exceptions: {bt["expected_exceptions"]:.2f}. Descriptive counts, not a model-validation pass. Every estimate uses only preceding observations.</div></section></div>
<footer>Research prototype. Demo prices, positions, shocks and limits are synthetic. No fees, FX, margin, liquidity, options or rolls. Snapshot imports are retrospective, not point-in-time historical vintages. Horizons are adjacent supplied observations; venue sessions are not verified. Positive risk values denote losses. Full precision and provenance: report.json; forecast audit: backtest.csv.</footer></html>"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["demo", "run"])
    parser.add_argument("--snapshot", type=Path)
    parser.add_argument("--book", type=Path)
    parser.add_argument("--scenarios", type=Path)
    parser.add_argument("--limits", type=Path)
    parser.add_argument("--window", type=int, default=100)
    parser.add_argument("--confidence", type=float, default=0.975)
    parser.add_argument("--output", type=Path, default=Path("output/demo"))
    args = parser.parse_args()
    if args.command == "demo":
        quotes, book, scenarios, provenance = demo()
        limits = {"hs_es": 15000.0, "gross_notional": 1500000.0, "stress_loss": 75000.0}
    else:
        if not all([args.snapshot, args.book, args.scenarios]):
            parser.error("run requires --snapshot, --book and --scenarios")
        book = pd.read_csv(args.book)
        quotes, provenance = platform_quotes(args.snapshot, book)
        scenarios = json.loads(args.scenarios.read_text())
        limits = json.loads(args.limits.read_text()) if args.limits else {}
    report, bt = analyze(quotes, book, scenarios, args.window, args.confidence, limits)
    report["provenance"] = provenance
    report["input_hashes"] = {
        "quotes": hashlib.sha256(quotes.to_csv(index=False).encode()).hexdigest(),
        "book": hashlib.sha256(book.to_csv(index=False).encode()).hexdigest(),
    }
    report["scenarios"] = scenarios
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "report.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    (args.output / "report.html").write_text(render(report, book))
    bt.to_csv(args.output / "backtest.csv", index=False)
    book.to_csv(args.output / "book.csv", index=False)
    quotes.to_csv(args.output / "quotes.csv", index=False)
    print(f"Report: {args.output / 'report.html'}")


if __name__ == "__main__":
    main()
