import json

import numpy as np
import pandas as pd
import pytest

from commodity_risk.cli import demo, platform_quotes, render
from commodity_risk.engine import (
    analyze,
    backtest,
    exposures,
    filtered_shocks,
    price_matrix,
    tail_risk,
)


def test_tail_fractional_mass_and_ties():
    # Worst 1.5 observations: (10 + 0.5*4)/1.5 = 8.
    assert tail_risk(np.array([1, 2, 3, 4, 10]), 0.7) == pytest.approx({"var": 4, "es": 8})
    assert tail_risk(np.array([1, 4, 4, 4]), 0.5) == {"var": 4, "es": 4}
    assert tail_risk(np.array([-3, -2, -1]), 0.9)["var"] == -1


@pytest.mark.parametrize("values,alpha", [([], 0.9), ([np.nan], 0.9), ([1], 1), ([1], 0)])
def test_invalid_tail_inputs(values, alpha):
    with pytest.raises(ValueError):
        tail_risk(np.array(values), alpha)


def test_hand_checked_signed_pnl_and_negative_prices():
    quotes, book, _, _ = demo()
    dates = pd.bdate_range("2025-01-01", periods=30)
    quotes = pd.DataFrame(
        [
            {"date": d, "contract": c, "unit": "USD/bbl", "price": -20 + i * (1 if j == 0 else 2)}
            for i, d in enumerate(dates)
            for j, c in enumerate(book.contract)
        ]
    )
    result, _ = analyze(quotes, book, {"down": dict(zip(book.contract, [-1.0, -2.0]))}, 22)
    assert result["daily_pnl"] == -4000  # 12*1000*1 - 8*1000*2
    assert result["stresses"]["down"] == 4000
    assert sum(result["contributions"].values()) == result["daily_pnl"]
    assert result["hs"]["es"] == pytest.approx(4000)


def test_no_lookahead_both_models():
    quotes, book, _, _ = demo()
    changes = price_matrix(quotes, book).diff().iloc[1:]
    for filtered in [False, True]:
        before = backtest(changes, exposures(book), 100, 0.975, filtered)
        altered = changes.copy()
        altered.iloc[140:] *= 100
        after = backtest(altered, exposures(book), 100, 0.975, filtered)
        pd.testing.assert_frame_equal(before.iloc[:40], after.iloc[:40])
        assert before.iloc[40]["var"] == after.iloc[40]["var"]
        assert before.iloc[40]["loss"] != after.iloc[40]["loss"]


def test_filtered_constant_shocks_and_scale_invariance():
    assert np.allclose(filtered_shocks(np.ones((30, 2))), 1)
    rng = np.random.default_rng(3)
    x = rng.normal(size=(80, 2))
    assert np.allclose(filtered_shocks(x * 10), filtered_shocks(x) * 10)


@pytest.mark.parametrize("failure", ["missing", "duplicate", "unit", "expiry", "nan"])
def test_quotes_fail_closed(failure):
    quotes, book, _, _ = demo()
    if failure == "missing":
        quotes = quotes.iloc[1:]
    elif failure == "duplicate":
        quotes = pd.concat([quotes, quotes.iloc[:1]])
    elif failure == "unit":
        quotes.loc[0, "unit"] = "USD/gal"
    elif failure == "expiry":
        book["expiry"] = "2025-02-01"
    else:
        quotes.loc[0, "price"] = np.nan
    with pytest.raises(ValueError):
        price_matrix(quotes, book)


def test_report_limits_and_stress_completeness():
    q, b, s, p = demo()
    r, bt = analyze(q, b, s, limits={"stress_loss": 1})
    assert r["limits"][0]["breach"]
    assert len(bt) == 259
    r["provenance"] = p
    assert "SYNTHETIC DEMONSTRATION" in render(r, b)
    with pytest.raises(ValueError):
        analyze(q, b, {"incomplete": {b.contract.iloc[0]: -1}})


def test_platform_schema_and_lineage(tmp_path):
    q, b, _, _ = demo()
    frame = q.rename(columns={"contract": "series", "price": "value"})
    frame["source"] = "fixture"
    frame["frequency"] = "daily"
    frame["kind"] = "futures_contract_close"
    frame["run_id"] = "fixture-run"
    frame["source_sha256"] = "fixture-hash"
    frame["dimensions"] = frame.series.map(
        lambda s: json.dumps(
            {"exchange": "DEMO", "contract": s.split(":")[1], "last_trade_date": "2027-01-01"}
        )
    )
    path = tmp_path / "snapshot.parquet"
    frame.to_parquet(path)
    quotes, provenance = platform_quotes(path, b)
    assert provenance["run_ids"] == ["fixture-run"]
    assert len(price_matrix(quotes, b)) == 360
    frame["kind"] = "spot"
    frame.to_parquet(path)
    with pytest.raises(ValueError):
        platform_quotes(path, b)


def test_integer_valued_float_quantities_render():
    q, b, s, p = demo()
    b["quantity"] = b.quantity.astype(float)
    r, _ = analyze(q, b, s)
    r["provenance"] = p
    assert "+12" in render(r, b)
