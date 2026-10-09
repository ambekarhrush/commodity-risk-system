"""Absolute price shocks support zero and negative futures prices."""

import math

import numpy as np
import pandas as pd


def tail_risk(losses: np.ndarray, confidence: float = 0.975) -> dict[str, float]:
    """Inverse empirical CDF VaR; ES integrates exactly the worst 1-alpha mass."""
    x = np.sort(np.asarray(losses, dtype=float))
    if x.ndim != 1 or not len(x) or not np.isfinite(x).all() or not 0 < confidence < 1:
        raise ValueError("Need finite one-dimensional losses and confidence in (0,1)")
    mass = len(x) * (1 - confidence)
    whole = math.floor(mass)
    fraction = mass - whole
    total = float(x[-whole:].sum()) if whole else 0.0
    if fraction:
        total += fraction * float(x[-whole - 1])
    return {"var": float(x[math.ceil(confidence * len(x)) - 1]), "es": total / mass}


def exposures(book: pd.DataFrame) -> pd.Series:
    required = {"contract", "quantity", "multiplier", "currency", "unit", "expiry"}
    if book.empty or not required.issubset(book) or book[list(required)].isna().any().any():
        raise ValueError("Incomplete position metadata")
    if book.contract.duplicated().any() or set(book.currency) != {"USD"}:
        raise ValueError("One net position per contract; USD only")
    if pd.to_datetime(book.expiry, errors="raise").isna().any():
        raise ValueError("Invalid expiry")
    numbers = book[["quantity", "multiplier"]].to_numpy(dtype=float)
    if not np.isfinite(numbers).all() or (book.multiplier <= 0).any():
        raise ValueError("Invalid quantity or multiplier")
    if (book.quantity % 1 != 0).any():
        raise ValueError("Futures quantities must be integers")
    return book.set_index("contract").quantity * book.set_index("contract").multiplier


def price_matrix(quotes: pd.DataFrame, book: pd.DataFrame) -> pd.DataFrame:
    weights = exposures(book)
    needed = {"date", "contract", "price", "unit"}
    if not needed.issubset(quotes) or quotes[list(needed)].isna().any().any():
        raise ValueError("Missing quote fields")
    q = quotes[quotes.contract.isin(weights.index)].copy()
    q["date"] = pd.to_datetime(q.date, errors="raise")
    if q.date.isna().any():
        raise ValueError("Invalid quote date")
    if q.duplicated(["date", "contract"]).any():
        raise ValueError("Duplicate contract/date")
    for row in book.itertuples():
        subset = q[q.contract == row.contract]
        if subset.empty or set(subset.unit) != {row.unit}:
            raise ValueError("Missing contract or mismatched price unit")
        if (subset.date >= pd.Timestamp(str(row.expiry))).any():
            raise ValueError("Quotes at/after expiry: explicit roll handling required")
    matrix = q.pivot(index="date", columns="contract", values="price").reindex(
        columns=weights.index
    )
    if len(matrix) < 3 or not np.isfinite(matrix.to_numpy(dtype=float)).all():
        raise ValueError("Incomplete synchronized history; no filling or silent date drops")
    return matrix.sort_index()


def filtered_shocks(changes: np.ndarray, decay: float = 0.94, warmup: int = 20) -> np.ndarray:
    """EWMA zero-mean variance; each innovation uses variance BEFORE its observation."""
    x = np.asarray(changes, dtype=float)
    if x.ndim != 2 or len(x) <= warmup or warmup < 2 or not 0 < decay < 1:
        raise ValueError("Insufficient filtered history or invalid EWMA parameters")
    if not np.isfinite(x).all():
        raise ValueError("Nonfinite shocks")
    variance = np.maximum(np.mean(x[:warmup] ** 2, axis=0), 1e-12)
    innovations = []
    for shock in x[warmup:]:
        innovations.append(shock / np.sqrt(variance))
        variance = np.maximum(decay * variance + (1 - decay) * shock**2, 1e-12)
    return np.asarray(innovations) * np.sqrt(variance)


def backtest(
    changes: pd.DataFrame,
    weights: pd.Series,
    window: int,
    confidence: float,
    filtered: bool = False,
) -> pd.DataFrame:
    if window < 22 or len(changes) <= window:
        raise ValueError("Need window >=22 and at least one out-of-sample observation")
    w = weights.reindex(changes.columns).to_numpy(dtype=float)
    rows = []
    for i in range(window, len(changes)):
        history = changes.iloc[i - window : i].to_numpy(dtype=float)
        shocks = filtered_shocks(history) if filtered else history
        risk = tail_risk(-shocks @ w, confidence)
        loss = float(-changes.iloc[i].to_numpy(dtype=float) @ w)
        rows.append(
            {
                "date": str(changes.index[i].date()),
                **risk,
                "loss": loss,
                "exception": loss > risk["var"],
            }
        )
    return pd.DataFrame(rows)


def analyze(
    quotes: pd.DataFrame,
    book: pd.DataFrame,
    scenarios: dict[str, dict[str, float]],
    window: int = 100,
    confidence: float = 0.975,
    limits: dict[str, float] | None = None,
) -> tuple[dict, pd.DataFrame]:
    prices = price_matrix(quotes, book)
    changes = prices.diff().iloc[1:]
    weights = exposures(book).reindex(prices.columns)
    history = changes.iloc[-window:].to_numpy(dtype=float)
    hs = tail_risk(-history @ weights.to_numpy(), confidence)
    fhs = tail_risk(-filtered_shocks(history) @ weights.to_numpy(), confidence)
    bt = backtest(changes, weights, window, confidence)
    fbt = backtest(changes, weights, window, confidence, filtered=True)
    bt = bt.merge(fbt, on="date", suffixes=("_hs", "_fhs"), validate="one_to_one")
    contributions = changes.iloc[-1] * weights
    stresses = {}
    for name, shocks in scenarios.items():
        if set(shocks) != set(weights.index) or not np.isfinite(list(shocks.values())).all():
            raise ValueError("Every stress must explicitly shock every held contract")
        stresses[name] = float(sum(weights[c] * shocks[c] for c in weights.index))
    historical = changes @ weights
    gross = float((prices.iloc[-1] * weights).abs().sum())
    measures = {
        "hs_var": hs["var"],
        "hs_es": hs["es"],
        "fhs_es": fhs["es"],
        "gross_notional": gross,
        "stress_loss": max([0.0] + [-p for p in stresses.values()]),
    }
    breaches = []
    for key, limit in (limits or {}).items():
        if key not in measures or not math.isfinite(limit) or limit < 0:
            raise ValueError("Unknown limit measure or invalid threshold")
        breaches.append(
            {
                "measure": key,
                "value": measures[key],
                "limit": limit,
                "breach": measures[key] > limit,
            }
        )
    report = {
        "as_of": str(prices.index[-1].date()),
        "confidence": confidence,
        "window": window,
        "observations": len(prices),
        "currency": "USD",
        "hs": hs,
        "fhs": fhs,
        "daily_pnl": float(contributions.sum()),
        "contributions": {str(k): float(v) for k, v in contributions.items()},
        "gross_notional": gross,
        "stresses": stresses,
        "worst_observed_shock": {
            "date": str(pd.Timestamp(str(historical.idxmin())).date()),
            "pnl": float(historical.min()),
        },
        "backtest": {
            "observations": len(bt),
            "hs_exceptions": int(bt.exception_hs.sum()),
            "fhs_exceptions": int(bt.exception_fhs.sum()),
            "expected_exceptions": len(bt) * (1 - confidence),
        },
        "limits": breaches,
    }
    return report, bt
