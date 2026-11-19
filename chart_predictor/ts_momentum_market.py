"""Fixed-rule, read-only daily crypto time-series momentum research."""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

SYMBOLS = ("BTCUSDT", "ETHUSDT", "BNBUSDT", "DOGEUSDT", "SOLUSDT", "XRPUSDT")
DAY_MS = 86_400_000
MINUTE_MS = 60_000
START_MS = 1_600_128_000_000  # 2020-09-15T00:00:00Z
END_MS = 1_704_067_200_000  # 2024-01-01T00:00:00Z, exclusive


@dataclass(frozen=True)
class DailyPanel:
    days: np.ndarray
    opens: np.ndarray
    closes: np.ndarray
    source_rows: int
    panel_sha256: str


def load_daily(db_path: str | Path, start_ms: int = START_MS, end_ms: int = END_MS) -> DailyPanel:
    """Aggregate only complete, contiguous UTC days from a read-only SQLite DB."""
    uri = Path(db_path).resolve().as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    try:
        conn.execute("PRAGMA query_only=ON")
        marks = ",".join("?" for _ in SYMBOLS)
        rows = conn.execute(
            f"""SELECT symbol, (open_ms / ?) AS day_id, COUNT(*) AS n,
                       MIN(open_ms), MAX(open_ms),
                       MAX(CASE WHEN open_ms = (open_ms / ?) * ? THEN open END),
                       MAX(CASE WHEN open_ms = (open_ms / ?) * ? + ? THEN close END),
                       SUM(CASE WHEN high < open OR high < close OR low > open
                                      OR low > close OR high < low THEN 1 ELSE 0 END),
                       SUM(CASE WHEN open_ms % ? <> 0 THEN 1 ELSE 0 END)
                  FROM candles
                 WHERE symbol IN ({marks}) AND open_ms >= ? AND open_ms < ?
                 GROUP BY symbol, day_id
                 ORDER BY day_id, symbol""",
            (DAY_MS, DAY_MS, DAY_MS, DAY_MS, DAY_MS, 1439 * MINUTE_MS, MINUTE_MS,
             *SYMBOLS, start_ms, end_ms),
        ).fetchall()
        source_rows = sum(int(row[2]) for row in rows)
    finally:
        conn.close()

    grouped: dict[int, dict[str, tuple[float, float]]] = {}
    bad: list[tuple[str, int, int, int, int, int]] = []
    for symbol, day_id, count, first_ms, last_ms, day_open, day_close, invalid, off_grid in rows:
        expected_open = int(day_id) * DAY_MS
        expected_last = expected_open + 1439 * MINUTE_MS
        if (count != 1440 or first_ms != expected_open or last_ms != expected_last or off_grid
                or invalid or day_open is None or day_close is None):
            bad.append((symbol, day_id, count, first_ms, last_ms, off_grid))
            continue
        grouped.setdefault(int(day_id), {})[symbol] = (float(day_open), float(day_close))

    expected_days = np.arange(start_ms // DAY_MS, end_ms // DAY_MS, dtype=np.int64)
    if bad:
        raise ValueError(f"Incomplete/invalid UTC daily bars; refusing repair/drop: {bad[:5]}")
    if len(grouped) != len(expected_days) or any(set(grouped.get(int(d), {})) != set(SYMBOLS) for d in expected_days):
        raise ValueError("Expected contiguous common daily coverage for all fixed symbols; refusing partial panel")
    opens = np.asarray([[grouped[int(d)][s][0] for s in SYMBOLS] for d in expected_days], dtype=np.float64)
    closes = np.asarray([[grouped[int(d)][s][1] for s in SYMBOLS] for d in expected_days], dtype=np.float64)
    if not np.isfinite(opens).all() or not np.isfinite(closes).all() or (opens <= 0).any() or (closes <= 0).any():
        raise ValueError("Invalid daily prices")
    digest = hashlib.sha256()
    digest.update(expected_days.astype("<i8", copy=False).tobytes())
    digest.update(opens.astype("<f8", copy=False).tobytes())
    digest.update(closes.astype("<f8", copy=False).tobytes())
    return DailyPanel(expected_days, opens, closes, source_rows, digest.hexdigest())


def market_close_index(closes: np.ndarray) -> np.ndarray:
    """Daily close index of a daily rebalanced equal-weight basket."""
    prices = np.asarray(closes, dtype=np.float64)
    if prices.ndim != 2 or prices.shape[1] != len(SYMBOLS) or len(prices) < 2:
        raise ValueError("closes must be days x six symbols")
    daily = np.mean(prices[1:] / prices[:-1] - 1.0, axis=1)
    return np.r_[1.0, np.cumprod(1.0 + daily)]


def signal_series(closes: np.ndarray, lookback: int = 28, holding: int = 5,
                  min_history: int = 252) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Causal expanding-history top-tercile long signal and lagged exposure."""
    if lookback <= 0 or holding <= 0 or min_history <= 0:
        raise ValueError("lookback, holding, and min_history must be positive")
    index = market_close_index(closes)
    n = len(index)
    trailing = np.full(n, np.nan, dtype=np.float64)
    if n > lookback:
        trailing[lookback:] = index[lookback:] / index[:-lookback] - 1.0
    signal = np.zeros(n, dtype=bool)
    eligible = np.zeros(n, dtype=bool)
    for t in range(lookback + min_history, n):
        history = trailing[lookback:t]
        history = history[np.isfinite(history)]
        if len(history) < min_history:
            continue
        cutoff = float(np.quantile(history, 2.0 / 3.0, method="linear"))
        eligible[t] = True
        signal[t] = trailing[t] >= cutoff
    exposure = np.zeros(n, dtype=np.float64)
    for t in range(1, n):
        lo = max(0, t - holding)
        exposure[t] = float(signal[lo:t].sum()) / holding
    return signal, eligible, exposure


def simulate(open_prices: np.ndarray, close_prices: np.ndarray, exposure: np.ndarray,
             cost_per_side: float) -> dict[str, Any]:
    """One-times long-only portfolio with daily open execution and close marks."""
    op = np.asarray(open_prices, dtype=np.float64)
    cl = np.asarray(close_prices, dtype=np.float64)
    exp = np.asarray(exposure, dtype=np.float64)
    if op.shape != cl.shape or op.ndim != 2 or op.shape[1] != len(SYMBOLS) or exp.shape != (len(op),):
        raise ValueError("panel shape mismatch")
    if not (0 <= cost_per_side < 0.1) or not np.isfinite(op).all() or not np.isfinite(cl).all():
        raise ValueError("invalid prices or cost")
    if (op <= 0).any() or (cl <= 0).any() or ((exp < 0) | (exp > 1)).any():
        raise ValueError("prices must be positive and exposure in [0,1]")

    n, assets = op.shape
    nav = 1.0
    weights = np.zeros(assets, dtype=np.float64)
    close_nav = np.ones(n, dtype=np.float64)
    daily_returns = np.zeros(n, dtype=np.float64)
    daily_turnover = np.zeros(n, dtype=np.float64)
    daily_cost = np.zeros(n, dtype=np.float64)
    daily_exposure = np.zeros(n, dtype=np.float64)

    # Buy the first target at the first open (normally cash during warm-up).
    target = np.full(assets, exp[0] / assets)
    turnover = float(np.abs(target - weights).sum())
    fee = cost_per_side * turnover
    nav *= 1.0 - fee
    weights = target
    daily_turnover[0], daily_cost[0], daily_exposure[0] = turnover, fee, float(target.sum())
    nav_before = nav
    intraday = cl[0] / op[0] - 1.0
    growth = 1.0 + float(np.dot(weights, intraday))
    nav *= growth
    if growth > 0:
        weights = weights * (1.0 + intraday) / growth
    close_nav[0] = nav
    daily_returns[0] = nav / nav_before - 1.0

    for t in range(1, n):
        nav_before = nav
        overnight = op[t] / cl[t - 1] - 1.0
        growth = 1.0 + float(np.dot(weights, overnight))
        if growth <= 0:
            raise ValueError("non-positive portfolio equity during overnight mark")
        nav *= growth
        weights = weights * (1.0 + overnight) / growth

        target = np.full(assets, exp[t] / assets)
        turnover = float(np.abs(target - weights).sum())
        fee = cost_per_side * turnover
        nav *= 1.0 - fee
        weights = target

        intraday = cl[t] / op[t] - 1.0
        growth = 1.0 + float(np.dot(weights, intraday))
        if growth <= 0:
            raise ValueError("non-positive portfolio equity during intraday mark")
        nav *= growth
        weights = weights * (1.0 + intraday) / growth
        daily_turnover[t], daily_cost[t], daily_exposure[t] = turnover, fee, float(target.sum())
        close_nav[t] = nav
        daily_returns[t] = nav / nav_before - 1.0

    # Final close liquidation is charged explicitly.
    final_turnover = float(np.abs(weights).sum())
    final_cost = cost_per_side * final_turnover
    nav *= 1.0 - final_cost
    close_nav[-1] = nav
    daily_returns[-1] = nav / close_nav[-2] - 1.0 if n > 1 else nav - 1.0
    daily_turnover[-1] += final_turnover
    daily_cost[-1] += final_cost
    return {
        "nav": nav, "curve": close_nav, "daily_returns": daily_returns,
        "turnover": daily_turnover, "cost": daily_cost, "exposure": daily_exposure,
    }


def passive(open_prices: np.ndarray, close_prices: np.ndarray, cost_per_side: float,
            asset_index: int | None = None) -> dict[str, Any]:
    """Buy-and-hold basket or one asset, including entry and terminal liquidation."""
    op = np.asarray(open_prices, dtype=np.float64)
    cl = np.asarray(close_prices, dtype=np.float64)
    if asset_index is None:
        weights = np.full(op.shape[1], 1.0 / op.shape[1])
    else:
        weights = np.zeros(op.shape[1]); weights[asset_index] = 1.0
    nav = 1.0 - cost_per_side * float(np.abs(weights).sum())
    curve = np.empty(len(op), dtype=np.float64)
    curve[0] = nav * (1.0 + float(np.dot(weights, cl[0] / op[0] - 1.0)))
    for t in range(1, len(op)):
        overnight = op[t] / cl[t - 1] - 1.0
        intra = cl[t] / op[t] - 1.0
        ret = float(np.dot(weights, overnight))
        nav *= 1.0 + ret
        weights = weights * (1.0 + overnight) / (1.0 + ret)
        ret = float(np.dot(weights, intra))
        nav *= 1.0 + ret
        weights = weights * (1.0 + intra) / (1.0 + ret)
        curve[t] = nav
    nav *= 1.0 - cost_per_side * float(np.abs(weights).sum())
    curve[-1] = nav
    return {"nav": nav, "curve": curve}


def summary(curve: np.ndarray, days: np.ndarray, daily_returns: np.ndarray | None = None) -> dict[str, float]:
    curve = np.asarray(curve, dtype=np.float64)
    dd = float(np.max(1.0 - curve / np.maximum.accumulate(np.r_[1.0, curve])[1:]))
    elapsed_years = (int(days[-1]) - int(days[0]) + 1) / 365.2425
    cagr = float(curve[-1] ** (1.0 / elapsed_years) - 1.0) if curve[-1] > 0 else -1.0
    returns = np.diff(np.r_[1.0, curve]) / np.r_[1.0, curve[:-1]]
    vol = float(np.std(returns, ddof=1)) if len(returns) > 1 else 0.0
    sharpe = float(np.mean(returns) / vol * np.sqrt(365.2425)) if vol > 0 else 0.0
    return {"final_nav": float(curve[-1]), "total_return": float(curve[-1] - 1.0),
            "cagr": cagr, "mdd": dd, "sharpe": sharpe}


def run(db_path: str | Path, out_path: str | Path) -> dict[str, Any]:
    panel = load_daily(db_path)
    results: dict[str, Any] = {
        "study": "fixed_market_time_series_momentum_28_5",
        "source": "Binance Vision USD-M 1m candles, historical research only",
        "symbols": list(SYMBOLS),
        "window_utc": ["2020-09-15", "2023-12-31"],
        "source_rows": panel.source_rows,
        "daily_panel_sha256": panel.panel_sha256,
        "note": "Funding unavailable; USD-M results are optimistic price-only proxies.",
        "configurations": {},
    }
    configs = [(28, 5, "primary"), (25, 4, "neighbor_25_4"), (25, 6, "neighbor_25_6"),
               (31, 4, "neighbor_31_4"), (31, 6, "neighbor_31_6")]
    for lookback, holding, name in configs:
        signal, eligible, exposure = signal_series(panel.closes, lookback, holding, 252)
        cell: dict[str, Any] = {
            "lookback_days": lookback, "holding_days": holding,
            "eligible_signal_days": int(eligible.sum()), "long_signal_days": int(signal.sum()),
            "mean_target_exposure": float(exposure.mean()),
            "base": {}, "stress": {},
        }
        for case, cost in (("base", 0.0009), ("stress", 0.0013)):
            strategy = simulate(panel.opens, panel.closes, exposure, cost)
            basket = passive(panel.opens, panel.closes, cost)
            btc = passive(panel.opens, panel.closes, cost, 0)
            cell[case] = {
                "strategy": summary(strategy["curve"], panel.days),
                "equal_weight_buy_hold": summary(basket["curve"], panel.days),
                "btc_buy_hold": summary(btc["curve"], panel.days),
                "cash_final_nav": 1.0,
                "turnover_total": float(strategy["turnover"].sum()),
                "sum_daily_cost_fraction": float(strategy["cost"].sum()),
                "mean_daily_exposure": float(np.mean(strategy["exposure"])),
                "annual_returns": _annual_returns(strategy["curve"], panel.days),
            }
            if name == "primary":
                cell[case]["walk_forward_chronology"] = _half_sample(strategy["curve"], panel.days)
                cell[case]["monte_carlo_trade_order"] = _monte_carlo_mdd(
                    strategy["daily_returns"], seed=4202026, repetitions=1000)
                cell[case]["seven_day_block_bootstrap"] = _block_bootstrap(
                    strategy["daily_returns"], seed=5202026, repetitions=1000, block_days=7)
        results["configurations"][name] = cell
    primary = results["configurations"]["primary"]

    def year_concentration(annual: dict[str, float]) -> float:
        growth = [float(np.log1p(value)) for value in annual.values() if value > 0]
        return max(growth) / sum(growth) if growth else 1.0

    gates = {
        "base_positive_cagr_sharpe": primary["base"]["strategy"]["cagr"] > 0
            and primary["base"]["strategy"]["sharpe"] > 0,
        "stress_positive_cagr_sharpe": primary["stress"]["strategy"]["cagr"] > 0
            and primary["stress"]["strategy"]["sharpe"] > 0,
        "base_beats_cash_basket_btc": primary["base"]["strategy"]["final_nav"] > 1.0
            and primary["base"]["strategy"]["final_nav"] > primary["base"]["equal_weight_buy_hold"]["final_nav"]
            and primary["base"]["strategy"]["final_nav"] > primary["base"]["btc_buy_hold"]["final_nav"],
        "stress_beats_cash_basket_btc": primary["stress"]["strategy"]["final_nav"] > 1.0
            and primary["stress"]["strategy"]["final_nav"] > primary["stress"]["equal_weight_buy_hold"]["final_nav"]
            and primary["stress"]["strategy"]["final_nav"] > primary["stress"]["btc_buy_hold"]["final_nav"],
        "base_mdd_below_basket_buy_hold": primary["base"]["strategy"]["mdd"]
            < primary["base"]["equal_weight_buy_hold"]["mdd"],
        "stress_mdd_below_basket_buy_hold": primary["stress"]["strategy"]["mdd"]
            < primary["stress"]["equal_weight_buy_hold"]["mdd"],
        "positive_log_growth_not_concentrated": year_concentration(
            primary["base"]["annual_returns"]) <= 0.60,
    }
    results["primary_development_gates"] = gates
    results["primary_gate_contribution_largest_year_fraction"] = year_concentration(
        primary["base"]["annual_returns"])
    results["decision"] = ("CONTINUE_TO_SINGLE_2024_PLUS_CONFIRMATION" if all(gates.values())
                           else "REJECT; KEEP_2024_PLUS_UNOPENED")
    output = Path(out_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(results, indent=2, sort_keys=True, allow_nan=False) + "\n")
    return results


def _annual_returns(curve: np.ndarray, days: np.ndarray) -> dict[str, float]:
    years: dict[str, float] = {}
    previous = 1.0
    day_years = [datetime.fromtimestamp(int(d) * 86400, tz=timezone.utc).year for d in days]
    for year in sorted(set(day_years)):
        mask = np.asarray([item == year for item in day_years])
        end_nav = float(curve[np.flatnonzero(mask)[-1]])
        years[str(year)] = end_nav / previous - 1.0
        previous = end_nav
    return years


def _half_sample(curve: np.ndarray, days: np.ndarray) -> dict[str, Any]:
    mid = len(curve) // 2
    return {
        "first_half": {"start_day": int(days[0]), "end_day": int(days[mid - 1]),
                       "nav_multiple": float(curve[mid - 1])},
        "second_half": {"start_day": int(days[mid]), "end_day": int(days[-1]),
                        "nav_multiple": float(curve[-1] / curve[mid - 1])},
        "note": "Frozen chronological diagnostic only; no parameters were fitted.",
    }


def _curve_mdd(returns: np.ndarray) -> float:
    nav = np.cumprod(1.0 + returns)
    peak = np.maximum.accumulate(np.r_[1.0, nav])[1:]
    return float(np.max(1.0 - nav / peak))


def _monte_carlo_mdd(returns: np.ndarray, seed: int, repetitions: int) -> dict[str, float | int]:
    rng = np.random.default_rng(seed)
    source = np.asarray(returns, dtype=np.float64)
    mdds = np.empty(repetitions, dtype=np.float64)
    for i in range(repetitions):
        mdds[i] = _curve_mdd(rng.permutation(source))
    return {"repetitions": repetitions, "seed": seed,
            "mdd_95pct": float(np.quantile(mdds, 0.95)),
            "mdd_median": float(np.quantile(mdds, 0.50)),
            "observed_order_mdd": _curve_mdd(source)}


def _block_bootstrap(returns: np.ndarray, seed: int, repetitions: int,
                     block_days: int) -> dict[str, float | int | list[float]]:
    rng = np.random.default_rng(seed)
    source = np.asarray(returns, dtype=np.float64)
    n = len(source)
    if n < block_days:
        raise ValueError("not enough daily returns for block bootstrap")
    means = np.empty(repetitions, dtype=np.float64)
    cagrs = np.empty(repetitions, dtype=np.float64)
    blocks_needed = int(np.ceil(n / block_days))
    offsets = np.arange(block_days)
    for i in range(repetitions):
        starts = rng.integers(0, n, size=blocks_needed)
        index = np.concatenate([(start + offsets) % n for start in starts])[:n]
        sample = source[index]
        means[i] = np.mean(sample) * 365.2425
        final = float(np.prod(1.0 + sample))
        cagrs[i] = final ** (365.2425 / n) - 1.0 if final > 0 else -1.0
    return {"repetitions": repetitions, "seed": seed, "block_days": block_days,
            "annualized_arithmetic_mean_ci95": [float(np.quantile(means, 0.025)),
                                                  float(np.quantile(means, 0.975))],
            "cagr_ci95": [float(np.quantile(cagrs, 0.025)),
                          float(np.quantile(cagrs, 0.975))]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    result = run(args.db, args.out)
    print(json.dumps({"study": result["study"], "configurations": list(result["configurations"]),
                      "out": str(args.out)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
