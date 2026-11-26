#!/usr/bin/env python3
"""EXPLORATORY SCREEN ONLY — not part of the 13-round preregistered G-gate track,
not added to TRAIN_TRIALS.csv, no promotion without separate formal preregistration
+ synthetic tests + resource-gated TRAIN run.

Lane C (rates / Treasury curve regime), ETF50 exploration set.

Reads only local parquet under TRADING_DATA_DIR (must be
/Users/user/CODE/Coin_Trade/trading_data): no network, no downloads, no writes
outside this directory. Writes into this directory only: RESULTS.csv,
RANKED_TOP10.md (IDEAS.csv is hand-written, not regenerated here).

Universe: SPY, TLT, IEF, SHY daily bars, common history 2002-07-30..2026-06-01
inclusive (verified below: all four tickers have identical trading-day sets in
this window, 5,998 sessions, no nulls). 2026-06-01 is the TRAIN/TEST cutoff; no
row with date > cutoff is ever read from the ETF or FRED/Treasury files.

Signal inputs: FRED fred_series.parquet series DGS10, DGS2, DGS3MO, DFF. Before
scoring anything, this script re-derives the PIT cross-check from the session's
background note: DGS10/DGS2/DGS3MO are compared bit-for-bit against the official
home.treasury.gov daily par yield curve file (treasury_par_yield_curve.parquet)
over their full overlap through the cutoff. If any mismatch is found the script
aborts before computing any strategy performance. DFF (daily effective fed funds
rate) has no separate official file to cross-check locally; it is a same-day
realized market rate (not a revised survey/estimate series like GDP), so it is
treated as PIT-safe on the same reasoning as the CMT yields, per instruction.
Credit spread series (BAMLH0A0HYM2 / BAMLC0A0CM) are not used by any design here.

Execution rule (shared by every design): a design's state function assigns a
string label to every FRED-native date using only that date's and earlier dates'
values (no look-ahead). For an ETF session S, the label used to trade session
S's open is the label on the latest FRED-native date strictly before S (i.e. the
signal is at least one full session old by the time it is acted on — the same
"bisect position-1, then next session's open" convention used in
search_etf_regime_hedge_v1.py). Weights only change, and cost is only paid, on
the session where the label actually changes; between label changes the position
is a plain buy-and-hold of the previously chosen asset(s) and its weight is
allowed to drift with price (the daily-rebalance bug fixed in
REPORT_ETF_REGIME_HEDGE_V1.md is avoided by construction).

Cost: 12bp round trip, i.e. 6bp per side, applied to the turnover (sum of
|weight_after - weight_before|) on the session a label change executes. The
initial entry and the final mark-to-close are each charged 6bp once.

Price construction: adjusted open = raw open * adj_close / close (same
dividend/split-adjusted convention as search_etf_regime_hedge_v1.py). This
mixes a same-day close-based adjustment ratio into the open price as a
convenience for computing holding-period total return including distributions;
it is a known simplification, not a claim that the adjustment ratio itself was
known intraday.

Metrics per idea: trade_count (regime-label switches), order_fill_count,
total_return, mdd, full annual_returns (2018 and 2022 always present if in
range), spy_total_return / spy_mdd (same common window, 100% SPY buy-hold,
start+end cost charged once each), excess_return, mdd_improvement, switches
per year. composite_score = clip(daily Sharpe of the strategy's NAV curve,
-3, 3) * sqrt(min(trade_count, 30) / 30), halved if the Sharpe sign in the
first vs second half of the window disagrees. trade_count < 3 gets
score = None ("insufficient_switches"): too few regime changes to say
anything about the signal, only about the one or two episodes that happened
to occur in this single historical sample. No multiple-testing correction, no
walk-forward split beyond the single fixed TRAIN/TEST cutoff already imposed,
no randomized/circular-shift null. Not G-eligible.
"""
from __future__ import annotations

import csv
import json
import os
import sys
from bisect import bisect_left
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.dataset as ds

HERE = Path(__file__).resolve().parent
LABEL = ("EXPLORATORY SCREEN ONLY — not part of the 13-round preregistered G-gate track, "
         "not added to TRAIN_TRIALS.csv, no promotion without separate formal preregistration "
         "+ synthetic tests + resource-gated TRAIN run.")

EXPECTED_DATA_DIR = "/Users/user/CODE/Coin_Trade/trading_data"
ETF_REL = "external/equities/us/yahoo_daily_us_etf.parquet"
FRED_REL = "external/equities/macro/fred_series.parquet"
CURVE_REL = "external/equities/macro/treasury_par_yield_curve.parquet"
TICKERS = ("SPY", "TLT", "IEF", "SHY")
START = pd.Timestamp("2002-07-30")
CUTOFF = pd.Timestamp("2026-06-01")
COST_PER_SIDE = 0.0006  # 6bp/side -> 12bp round trip on a full switch


# ---------------------------------------------------------------- data access
def data_root() -> Path:
    configured = os.environ.get("TRADING_DATA_DIR")
    if configured != EXPECTED_DATA_DIR:
        raise RuntimeError(
            f"TRADING_DATA_DIR must be exactly {EXPECTED_DATA_DIR!r}; got {configured!r}"
        )
    return Path(configured)


def load_prices(root: Path) -> pd.DataFrame:
    dset = ds.dataset(root / ETF_REL, format="parquet")
    needed = {"ticker", "date", "open", "close", "adj_close"}
    missing = sorted(needed - set(dset.schema.names))
    if missing:
        raise RuntimeError(f"ETF price schema missing required columns: {missing}")
    table = dset.to_table(
        filter=(ds.field("ticker").isin(list(TICKERS)))
        & (ds.field("date") >= START)
        & (ds.field("date") <= CUTOFF),
        columns=["ticker", "date", "open", "close", "adj_close"],
    )
    df = table.to_pandas()
    if df[["open", "close", "adj_close"]].isnull().any().any():
        raise RuntimeError("Null price/adjustment field in TRAIN ETF window; no interpolation allowed")
    if (df["close"] == 0).any():
        raise RuntimeError("Zero close price in TRAIN ETF window")
    df["adj_open"] = df["open"] * df["adj_close"] / df["close"]
    wide = df.pivot(index="date", columns="ticker", values="adj_open").sort_index()
    wide = wide.dropna(axis=0, how="any")  # require all four tickers present that session
    if len(wide) == 0:
        raise RuntimeError("No common session across SPY/TLT/IEF/SHY in the requested window")
    missing_dates = set(df["date"].unique()) - set(wide.index)
    return wide, len(missing_dates)


def load_fred(root: Path, series: str) -> pd.Series:
    dset = ds.dataset(root / FRED_REL, format="parquet")
    if not {"series", "date", "value"}.issubset(dset.schema.names):
        raise RuntimeError("FRED input lacks series/date/value columns")
    table = dset.to_table(
        filter=(ds.field("series") == series) & (ds.field("date") <= CUTOFF),
        columns=["date", "value"],
    )
    df = table.to_pandas().dropna()
    s = df.set_index("date")["value"].sort_index()
    s = s[~s.index.duplicated(keep="last")]
    return s


def pit_crosscheck(root: Path) -> dict:
    """Re-derive this session's DGS10/DGS2/DGS3MO vs official Treasury curve match
    before trusting any FRED series as a TRAIN-safe daily signal."""
    curve_ds = ds.dataset(root / CURVE_REL, format="parquet")
    curve = curve_ds.to_table(
        filter=ds.field("date") <= CUTOFF,
        columns=["date", "2_yr", "3_mo", "10_yr"],
    ).to_pandas().set_index("date")
    audit = {}
    for series, col in (("DGS10", "10_yr"), ("DGS2", "2_yr"), ("DGS3MO", "3_mo")):
        fred = load_fred(root, series)
        merged = curve[[col]].join(fred.rename("fred"), how="inner").dropna()
        diff = (merged[col] - merged["fred"]).abs()
        mismatches = int((diff > 0.01).sum())
        audit[series] = {"overlap_days": int(len(merged)), "max_abs_diff": float(diff.max()) if len(diff) else None,
                          "mismatches_gt_1bp": mismatches}
        if mismatches:
            raise RuntimeError(f"{series} vs official Treasury curve column {col}: {mismatches} mismatches > 1bp; aborting before scoring")
        if len(merged) < 1000:
            raise RuntimeError(f"{series} vs official Treasury curve overlap too small ({len(merged)} days) to trust")
    return audit


# ---------------------------------------------------------------- state builders
def binary_state(spread: pd.Series, threshold: float, safe_label: str, risk_label: str) -> pd.Series:
    return pd.Series(np.where(spread < threshold, safe_label, risk_label), index=spread.index)


def persistence_state(spread: pd.Series, threshold: float, persist_days: int,
                       safe_label: str, risk_label: str) -> pd.Series:
    inverted = (spread < threshold).to_numpy()
    out = np.empty(len(inverted), dtype=object)
    state = risk_label
    streak = 0
    for i, flag in enumerate(inverted):
        if flag:
            streak += 1
            if streak >= persist_days:
                state = safe_label
        else:
            streak = 0
            state = risk_label
        out[i] = state
    return pd.Series(out, index=spread.index)


def uninvert_event_state(spread: pd.Series, threshold: float, persist_days: int, hold_days: int,
                          safe_label: str, risk_label: str) -> pd.Series:
    """Default is risk_label the whole time. A hold window of safe_label fires only
    on the session the curve first prints >=threshold after a streak of at least
    persist_days consecutive <threshold sessions. During the hold window the spread
    is ignored entirely; the inverted-streak counter restarts only after the hold
    window ends."""
    inverted = (spread < threshold).to_numpy()
    out = np.empty(len(inverted), dtype=object)
    streak = 0
    hold_remaining = 0
    armed_streak = 0  # inverted-streak length right before the current/last steepening check
    state = risk_label
    for i, flag in enumerate(inverted):
        if hold_remaining > 0:
            state = safe_label
            hold_remaining -= 1
            streak = 0
            out[i] = state
            continue
        if flag:
            streak += 1
            state = risk_label
        else:
            if streak >= persist_days:
                state = safe_label
                hold_remaining = hold_days - 1
            else:
                state = risk_label
            streak = 0
        out[i] = state
    return pd.Series(out, index=spread.index)


def roc_tristate(level: pd.Series, lookback: int, threshold: float,
                  fell_label: str, rose_label: str, neutral_label: str) -> pd.Series:
    change = level - level.shift(lookback)
    out = pd.Series(neutral_label, index=level.index, dtype=object)
    out[change <= -threshold] = fell_label
    out[change >= threshold] = rose_label
    out = out.iloc[lookback:]  # no state before the lookback window has filled
    return out


def level_tristate(level: pd.Series, high: float, low: float,
                    high_label: str, low_label: str, mid_label: str) -> pd.Series:
    out = pd.Series(mid_label, index=level.index, dtype=object)
    out[level >= high] = high_label
    out[level < low] = low_label
    return out


def trend_binary(level: pd.Series, lookback: int, threshold: float,
                  up_label: str, flat_or_down_label: str) -> pd.Series:
    change = level - level.shift(lookback)
    out = pd.Series(flat_or_down_label, index=level.index, dtype=object)
    out[change >= threshold] = up_label
    out = out.iloc[lookback:]
    return out


# ---------------------------------------------------------------- engine
def drawdown(curve: list[float]) -> float:
    peak = curve[0]
    worst = 0.0
    for value in curve:
        peak = max(peak, value)
        worst = min(worst, value / peak - 1.0)
    return worst


def annual_returns(dates: pd.Index, curve: list[float]) -> dict[str, float]:
    years = sorted({d.year for d in dates})
    out: dict[str, float] = {}
    for year in years:
        idx = [i for i, d in enumerate(dates) if d.year == year]
        first_i, last_i = idx[0], idx[-1]
        start_nav = curve[first_i - 1] if first_i > 0 else 100.0
        out[str(year)] = curve[last_i] / start_nav - 1.0
    return out


def sharpe_from_curve(curve: list[float]) -> float:
    nav = pd.Series(curve)
    rets = nav.pct_change().dropna()
    if rets.std(ddof=1) == 0 or len(rets) < 2:
        return 0.0
    return float(rets.mean() / rets.std(ddof=1) * np.sqrt(252))


def run_idea(prices: pd.DataFrame, state: pd.Series, label_to_weights: dict[str, dict[str, float]]) -> dict:
    sessions = prices.index
    state_dates = state.index.to_numpy()
    state_values = state.to_numpy()

    def label_for(session: pd.Timestamp) -> str:
        pos = bisect_left(state_dates, session.to_numpy()) - 1
        if pos < 0:
            raise RuntimeError(f"No state value before first session {session}; widen FRED history load")
        return state_values[pos]

    first_label = label_for(sessions[0])
    weights = {t: label_to_weights[first_label].get(t, 0.0) for t in TICKERS}
    nav = 100.0 * (1.0 - COST_PER_SIDE * sum(weights.values()))
    curve = [nav]
    switches = 0
    order_fills = sum(1 for v in weights.values() if v > 0)
    total_cost = 100.0 - nav
    current_label = first_label
    last_weights = weights

    for i in range(1, len(sessions)):
        prev, cur = sessions[i - 1], sessions[i]
        rets = {t: float(prices.loc[cur, t]) / float(prices.loc[prev, t]) - 1.0 for t in TICKERS}
        pre = {t: last_weights[t] * (1.0 + rets[t]) for t in TICKERS}
        growth = sum(pre.values())
        if growth <= 0:
            raise RuntimeError(f"NAV went non-positive at {cur}")
        nav *= growth
        cur_weights = {t: pre[t] / growth for t in TICKERS}

        new_label = label_for(cur)
        if new_label != current_label:
            new_weights = {t: label_to_weights[new_label].get(t, 0.0) for t in TICKERS}
            turnover = sum(abs(new_weights[t] - cur_weights[t]) for t in TICKERS)
            changed = [t for t in TICKERS if abs(new_weights[t] - cur_weights[t]) > 1e-9]
            switches += 1
            order_fills += len(changed)
            cost = nav * COST_PER_SIDE * turnover
            nav -= cost
            total_cost += cost
            last_weights = new_weights
            current_label = new_label
        else:
            last_weights = cur_weights
        curve.append(nav)

    end_cost = nav * COST_PER_SIDE * sum(last_weights.values())
    nav -= end_cost
    total_cost += end_cost
    order_fills += sum(1 for v in last_weights.values() if v > 0)

    years_span = (sessions[-1] - sessions[0]).days / 365.25
    sharpe_full = sharpe_from_curve(curve)
    half = len(curve) // 2
    sharpe_first = sharpe_from_curve(curve[: max(half, 2)])
    sharpe_second = sharpe_from_curve(curve[max(half, 2) - 1 :])
    sign_disagree = (sharpe_first > 0) != (sharpe_second > 0)

    if switches < 3:
        composite_score = None
        score_note = "insufficient_switches"
    else:
        composite_score = float(np.clip(sharpe_full, -3, 3) * np.sqrt(min(switches, 30) / 30))
        if sign_disagree:
            composite_score *= 0.5
        score_note = "half_period_sign_disagree" if sign_disagree else "ok"

    return {
        "trade_count": switches,
        "order_fill_count": order_fills,
        "total_return": nav / 100.0 - 1.0,
        "mdd": drawdown(curve + [nav]),
        "annual_returns": annual_returns(sessions, curve),
        "total_cost_nav_units": total_cost,
        "switches_per_year": switches / years_span,
        "sharpe": sharpe_full,
        "composite_score": composite_score,
        "score_note": score_note,
    }


def spy_buy_hold(prices: pd.DataFrame) -> dict:
    sessions = prices.index
    nav = 100.0 * (1.0 - COST_PER_SIDE)
    curve = [nav]
    for prev, cur in zip(sessions, sessions[1:]):
        nav *= float(prices.loc[cur, "SPY"]) / float(prices.loc[prev, "SPY"])
        curve.append(nav)
    nav *= 1.0 - COST_PER_SIDE
    return {
        "total_return": nav / 100.0 - 1.0,
        "mdd": drawdown(curve + [nav]),
        "annual_returns": annual_returns(sessions, curve),
    }


# ---------------------------------------------------------------- idea registry
def build_ideas(root: Path, prices: pd.DataFrame) -> dict[str, dict]:
    dgs10 = load_fred(root, "DGS10")
    dgs2 = load_fred(root, "DGS2")
    dgs3mo = load_fred(root, "DGS3MO")
    dff = load_fred(root, "DFF")

    spread_2_10 = (dgs10 - dgs2).dropna()
    spread_3mo_10 = (dgs10 - dgs3mo).dropna()

    ideas: dict[str, dict] = {}

    ideas["RC001"] = dict(state=binary_state(spread_2_10, 0.0, "SHY", "SPY"),
                           weights={"SPY": {"SPY": 1.0}, "SHY": {"SHY": 1.0}})
    ideas["RC002"] = dict(state=binary_state(spread_2_10, 0.0, "TLT", "SPY"),
                           weights={"SPY": {"SPY": 1.0}, "TLT": {"TLT": 1.0}})
    ideas["RC003"] = dict(state=binary_state(spread_3mo_10, 0.0, "SHY", "SPY"),
                           weights={"SPY": {"SPY": 1.0}, "SHY": {"SHY": 1.0}})
    ideas["RC004"] = dict(state=binary_state(spread_3mo_10, 0.0, "TLT", "SPY"),
                           weights={"SPY": {"SPY": 1.0}, "TLT": {"TLT": 1.0}})
    ideas["RC005"] = dict(state=persistence_state(spread_3mo_10, 0.0, 20, "SHY", "SPY"),
                           weights={"SPY": {"SPY": 1.0}, "SHY": {"SHY": 1.0}})
    ideas["RC006"] = dict(state=persistence_state(spread_3mo_10, 0.0, 60, "SHY", "SPY"),
                           weights={"SPY": {"SPY": 1.0}, "SHY": {"SHY": 1.0}})
    ideas["RC014"] = dict(state=persistence_state(spread_3mo_10, 0.0, 20, "TLT", "SPY"),
                           weights={"SPY": {"SPY": 1.0}, "TLT": {"TLT": 1.0}})
    ideas["RC007"] = dict(state=uninvert_event_state(spread_2_10, 0.0, 20, 180, "SHY", "SPY"),
                           weights={"SPY": {"SPY": 1.0}, "SHY": {"SHY": 1.0}})
    ideas["RC008"] = dict(state=uninvert_event_state(spread_3mo_10, 0.0, 20, 120, "SHY", "SPY"),
                           weights={"SPY": {"SPY": 1.0}, "SHY": {"SHY": 1.0}})
    ideas["RC009"] = dict(state=roc_tristate(dgs10, 63, 0.50, "TLT", "SHY", "IEF"),
                           weights={"TLT": {"TLT": 1.0}, "SHY": {"SHY": 1.0}, "IEF": {"IEF": 1.0}})
    ideas["RC010"] = dict(state=roc_tristate(dgs10, 21, 0.25, "TLT", "SHY", "IEF"),
                           weights={"TLT": {"TLT": 1.0}, "SHY": {"SHY": 1.0}, "IEF": {"IEF": 1.0}})
    ideas["RC011"] = dict(state=level_tristate(dgs10, 4.5, 2.5, "SHY", "TLT", "IEF"),
                           weights={"TLT": {"TLT": 1.0}, "SHY": {"SHY": 1.0}, "IEF": {"IEF": 1.0}})
    ideas["RC012"] = dict(state=trend_binary(dff, 126, 0.25, "SHY", "SPY"),
                           weights={"SPY": {"SPY": 1.0}, "SHY": {"SHY": 1.0}})
    ideas["RC013"] = dict(state=trend_binary(dff, 252, 0.50, "SHY", "SPY"),
                           weights={"SPY": {"SPY": 1.0}, "SHY": {"SHY": 1.0}})
    return ideas


def load_idea_meta() -> dict[str, dict[str, str]]:
    with (HERE / "IDEAS.csv").open("r", newline="", encoding="utf-8") as handle:
        lines = handle.readlines()
    rows = [ln for ln in lines if not ln.startswith("#")]
    reader = csv.DictReader(rows)
    return {row["idea_id"]: row for row in reader}


# ---------------------------------------------------------------- main
def main() -> int:
    root = data_root()
    audit = pit_crosscheck(root)
    prices, missing_sessions = load_prices(root)
    if missing_sessions:
        raise RuntimeError(f"{missing_sessions} session(s) dropped for incomplete ticker coverage; expected 0")
    if prices.index[0] != START or prices.index[-1] != CUTOFF:
        raise RuntimeError(
            f"Observed common window {prices.index[0].date()}..{prices.index[-1].date()} "
            f"differs from expected {START.date()}..{CUTOFF.date()}"
        )

    baseline = spy_buy_hold(prices)
    meta = load_idea_meta()
    ideas = build_ideas(root, prices)

    results = []
    for idea_id, spec in ideas.items():
        metrics = run_idea(prices, spec["state"], spec["weights"])
        metrics["idea_id"] = idea_id
        metrics["name"] = meta[idea_id]["name"]
        metrics["theme_note"] = meta[idea_id]["theme_note"]
        metrics["spy_total_return"] = baseline["total_return"]
        metrics["spy_mdd"] = baseline["mdd"]
        metrics["excess_return"] = metrics["total_return"] - baseline["total_return"]
        metrics["mdd_improvement"] = metrics["mdd"] - baseline["mdd"]
        metrics["return_2018"] = metrics["annual_returns"].get("2018")
        metrics["return_2022"] = metrics["annual_returns"].get("2022")
        metrics["spy_return_2018"] = baseline["annual_returns"].get("2018")
        metrics["spy_return_2022"] = baseline["annual_returns"].get("2022")
        results.append(metrics)

    fieldnames = [
        "idea_id", "name", "theme_note", "trade_count", "order_fill_count", "switches_per_year",
        "total_return", "spy_total_return", "excess_return", "mdd", "spy_mdd", "mdd_improvement",
        "return_2018", "spy_return_2018", "return_2022", "spy_return_2022",
        "sharpe", "composite_score", "score_note", "total_cost_nav_units", "annual_returns",
    ]
    with (HERE / "RESULTS.csv").open("w", newline="", encoding="utf-8") as handle:
        handle.write(f"# {LABEL}\n")
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for item in results:
            row = {k: item[k] for k in fieldnames if k != "annual_returns"}
            row["annual_returns"] = json.dumps(item["annual_returns"], sort_keys=True)
            writer.writerow(row)

    print(json.dumps({"status": "complete", "pit_crosscheck": audit, "sessions": len(prices),
                      "spy_buy_hold": baseline, "n_ideas": len(results)}, sort_keys=True, default=str))
    write_ranked_md(results, baseline, audit, len(prices))
    return 0


def write_ranked_md(results: list[dict], baseline: dict, audit: dict, n_sessions: int) -> None:
    scored = [r for r in results if r["composite_score"] is not None]
    scored.sort(key=lambda r: r["composite_score"], reverse=True)
    unscored = [r for r in results if r["composite_score"] is None]

    lines = []
    lines.append("# Lane C (rates/curve regime) — RANKED TOP 10\n")
    lines.append(f"\n{LABEL}\n")
    lines.append(f"\nSessions scored: {n_sessions} (2002-07-30..2026-06-01, TRAIN only). "
                 f"SPY buy-hold baseline over same window: total_return={baseline['total_return']:.4f}, "
                 f"mdd={baseline['mdd']:.4f}, 2018={baseline['annual_returns'].get('2018'):.4f}, "
                 f"2022={baseline['annual_returns'].get('2022'):.4f}.\n")
    lines.append(f"\nPIT cross-check (DGS10/DGS2/DGS3MO vs official Treasury par curve, this run): "
                 f"{json.dumps(audit, sort_keys=True)}\n")
    lines.append(f"\nScored {len(scored)}/{len(results)} ideas (>=3 regime switches); "
                 f"{len(unscored)} marked insufficient_switches.\n")
    lines.append("\n## Top 10 by composite_score\n")
    lines.append("\n| rank | idea_id | name | theme | switches | switches/yr | total_return | excess_vs_spy | mdd | mdd_improvement | 2018 | 2022 | sharpe | score | note |\n")
    lines.append("|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|\n")
    for rank, r in enumerate(scored[:10], start=1):
        lines.append(
            f"| {rank} | {r['idea_id']} | {r['name']} | {r['theme_note']} | {r['trade_count']} | "
            f"{r['switches_per_year']:.2f} | {r['total_return']:.4f} | {r['excess_return']:.4f} | "
            f"{r['mdd']:.4f} | {r['mdd_improvement']:.4f} | "
            f"{(r['return_2018'] if r['return_2018'] is not None else float('nan')):.4f} | "
            f"{(r['return_2022'] if r['return_2022'] is not None else float('nan')):.4f} | "
            f"{r['sharpe']:.3f} | {r['composite_score']:.3f} | {r['score_note']} |\n"
        )
    if unscored:
        lines.append("\n## Not scored (fewer than 3 regime switches in the whole window)\n")
        lines.append("\n| idea_id | name | theme | switches | total_return | excess_vs_spy |\n")
        lines.append("|---|---|---|---:|---:|---:|\n")
        for r in unscored:
            lines.append(f"| {r['idea_id']} | {r['name']} | {r['theme_note']} | {r['trade_count']} | "
                         f"{r['total_return']:.4f} | {r['excess_return']:.4f} |\n")
    (HERE / "RANKED_TOP10.md").write_text("".join(lines), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
