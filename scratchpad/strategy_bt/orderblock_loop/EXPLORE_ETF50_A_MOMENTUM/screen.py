#!/usr/bin/env python3
"""
EXPLORE_ETF50_A_MOMENTUM -- exploratory low-fi screen only.

NOT part of the 13-round preregistration G-gate track. Does NOT append rows
to scratchpad/strategy_bt/orderblock_loop/TRAIN_TRIALS.csv. No multiple-testing
correction, no walk-forward, no PIT audit of macro vintages (only price data,
same-source Yahoo ETF daily bars, is used here).

Hard rule honored: TEST (date > 2026-06-01) is filtered out immediately on
load, before any computation, and is never read/printed/used.

Methodology notes (documented simplifications vs. the full PREREG track):
  - adj_close (Yahoo backward-adjusted close, dividends + splits) is used as
    a total-return price proxy for momentum/MA signals AND for daily returns.
  - Execution timing: "decide at close of day S using info through S, trade
    at the open of day S+1" is approximated by a 1-trading-day lag applied to
    a close-to-close return series (standard proxy widely used in this kind
    of fast screen; avoids needing a dividend/split-adjusted synthetic open).
  - Cost: 12bp round trip = 6bp (0.06%) per unit of one-way portfolio weight
    change, i.e. cost_t = 0.0006 * sum(|w_t - w_{t-1}|). A full flip between
    two 100% positions costs 0.0006*2 = 12bp, matching "round trip 12bp".
  - Each idea's evaluation window starts only once ALL tickers it uses have
    II  listed (per observed first row in the local Yahoo parquet) AND enough
    lookback history has accrued for the first valid signal. It ends at the
    common TRAIN cutoff 2026-06-01 (inclusive).
  - Baseline for every idea = 100% SPY buy & hold over that idea's own exact
    evaluation window, same entry/exit cost convention.

ADX(14) and ATR(14) (EM13/EM14 trend-strength gates) are computed on an
adjustment-factor-scaled OHLC (high/low/open * adj_close/close) so split
jumps don't create fake ranges; this keeps all internal signals on the same
adjusted-price basis as the momentum/MA signals.
"""
import json
import numpy as np
import pandas as pd

DATA_DIR = "/Users/user/CODE/Coin_Trade/trading_data"
ETF_PARQUET = f"{DATA_DIR}/external/equities/us/yahoo_daily_us_etf.parquet"
TRAIN_CUTOFF = pd.Timestamp("2026-06-01")
COST_PER_LEG = 0.0006  # 0.04% fee + 0.02% slippage, one-way, per unit weight change

OUT_DIR = "/Users/user/CODE/Coin_Trade/.claude/worktrees/agent-a97b3ec3513efb577/scratchpad/strategy_bt/orderblock_loop/EXPLORE_ETF50_A_MOMENTUM"


# ---------------------------------------------------------------------------
# Data loading (TEST filtered out immediately, before any other computation)
# ---------------------------------------------------------------------------

def load_panels():
    raw = pd.read_parquet(ETF_PARQUET)
    raw = raw[raw["date"] <= TRAIN_CUTOFF].copy()  # TRAIN-only, enforced at load time
    raw = raw.drop_duplicates(subset=["ticker", "date"], keep="first")
    raw = raw.sort_values(["ticker", "date"])

    tickers = sorted(raw["ticker"].unique())
    close = raw.pivot(index="date", columns="ticker", values="close")
    adj_close = raw.pivot(index="date", columns="ticker", values="adj_close")
    high = raw.pivot(index="date", columns="ticker", values="high")
    low = raw.pivot(index="date", columns="ticker", values="low")

    factor = adj_close / close
    adj_high = high * factor
    adj_low = low * factor

    listing_date = raw.groupby("ticker")["date"].min().to_dict()
    return adj_close, adj_high, adj_low, listing_date


ADJ_CLOSE, ADJ_HIGH, ADJ_LOW, LISTING_DATE = load_panels()
ALL_DATES = ADJ_CLOSE.index  # full TRAIN trading-day calendar (union of all tickers' dates)


# ---------------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------------

def common_dates(tickers):
    """Trading days on which every ticker in `tickers` has a non-NaN adj_close."""
    sub = ADJ_CLOSE[tickers].dropna(how="any")
    return sub.index


def month_end_signal_dates(dates):
    s = pd.Series(dates, index=dates)
    grp = s.groupby([dates.year, dates.month])
    return pd.DatetimeIndex(sorted(grp.max().values))


def wilder_ema(series, n):
    return series.ewm(alpha=1.0 / n, adjust=False, min_periods=n).mean()


def compute_adx14(ticker):
    h, l, c = ADJ_HIGH[ticker], ADJ_LOW[ticker], ADJ_CLOSE[ticker]
    up_move = h.diff()
    down_move = -l.diff()
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    prev_c = c.shift(1)
    tr = pd.concat([(h - l), (h - prev_c).abs(), (l - prev_c).abs()], axis=1).max(axis=1)
    atr14 = wilder_ema(tr, 14)
    plus_di = 100 * wilder_ema(pd.Series(plus_dm, index=c.index), 14) / atr14
    minus_di = 100 * wilder_ema(pd.Series(minus_dm, index=c.index), 14) / atr14
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
    adx = wilder_ema(dx, 14)
    return adx, atr14


def apply_lag_and_cost(weights_df, ret_df, eval_start, eval_end):
    """weights_df: target weight decided AS OF each date (index=all_dates, ffilled).
    Shift by 1 trading day -> active weight earning that day's return (approximates
    next-day-open execution of a close-based signal). Returns net daily return series,
    turnover count, and per-day weight-change diagnostics, restricted to [eval_start, eval_end].
    """
    active = weights_df.shift(1)
    idx = active.index[(active.index >= eval_start) & (active.index <= eval_end)]
    active = active.loc[idx]
    ret = ret_df.loc[idx]

    gross = (active * ret).sum(axis=1)
    delta = active.diff().abs().sum(axis=1)
    delta.iloc[0] = active.iloc[0].abs().sum()  # initial entry cost (from flat)
    cost = COST_PER_LEG * delta
    net = gross - cost

    # liquidation cost at the very last day (sell whatever is held)
    final_w = active.iloc[-1]
    liq_cost = COST_PER_LEG * final_w.abs().sum()
    net.iloc[-1] -= liq_cost

    n_rebalances = int((delta > 1e-9).sum())
    return net, n_rebalances, delta


def spy_baseline(eval_start, eval_end):
    px = ADJ_CLOSE["SPY"].loc[eval_start:eval_end].dropna()
    ret = px.pct_change().fillna(0.0)
    ret.iloc[0] -= COST_PER_LEG  # entry cost
    ret.iloc[-1] -= COST_PER_LEG  # exit cost
    return ret


def mdd(nav):
    roll_max = nav.cummax()
    dd = nav / roll_max - 1.0
    return dd.min()


def annual_returns(nav):
    yearly = nav.groupby(nav.index.year).agg(["first", "last"])
    out = {}
    for yr, row in yearly.iterrows():
        out[int(yr)] = row["last"] / row["first"] - 1.0
    return out


def summarize(idea_id, family, net_ret, n_rebalances, eval_start, eval_end, baseline_ret, extra_turnover_note=""):
    nav = (1.0 + net_ret).cumprod() * 100.0
    bnav = (1.0 + baseline_ret).cumprod() * 100.0

    total_ret = nav.iloc[-1] / 100.0 - 1.0
    base_total_ret = bnav.iloc[-1] / 100.0 - 1.0
    excess_ret = total_ret - base_total_ret

    strat_mdd = mdd(nav)
    base_mdd = mdd(bnav)
    mdd_improvement = strat_mdd - base_mdd  # positive = strategy MDD less negative than baseline (improvement)

    n_days = len(net_ret)
    n_years = n_days / 252.0
    cagr = (1.0 + total_ret) ** (1.0 / n_years) - 1.0 if n_years > 0 else np.nan
    base_cagr = (1.0 + base_total_ret) ** (1.0 / n_years) - 1.0 if n_years > 0 else np.nan

    ann_vol = net_ret.std() * np.sqrt(252)
    sharpe = (net_ret.mean() * 252) / ann_vol if ann_vol > 0 else np.nan

    ann_ret = annual_returns(nav)
    ret_2018 = ann_ret.get(2018, np.nan)
    ret_2022 = ann_ret.get(2022, np.nan)
    base_ann_ret = annual_returns(bnav)
    base_ret_2018 = base_ann_ret.get(2018, np.nan)
    base_ret_2022 = base_ann_ret.get(2022, np.nan)

    rebal_per_year = n_rebalances / n_years if n_years > 0 else np.nan

    return {
        "idea_id": idea_id,
        "family": family,
        "eval_start": str(eval_start.date()),
        "eval_end": str(eval_end.date()),
        "n_days": n_days,
        "n_years": round(n_years, 2),
        "n_rebalances": n_rebalances,
        "rebal_per_year": round(rebal_per_year, 2),
        "total_return_pct": round(total_ret * 100, 2),
        "cagr_pct": round(cagr * 100, 2),
        "baseline_spy_total_return_pct": round(base_total_ret * 100, 2),
        "baseline_spy_cagr_pct": round(base_cagr * 100, 2),
        "excess_return_pct": round(excess_ret * 100, 2),
        "strategy_mdd_pct": round(strat_mdd * 100, 2),
        "baseline_mdd_pct": round(base_mdd * 100, 2),
        "mdd_improvement_pct": round(mdd_improvement * 100, 2),
        "ann_vol_pct": round(ann_vol * 100, 2),
        "sharpe": round(sharpe, 3) if sharpe == sharpe else None,
        "return_2018_pct": round(ret_2018 * 100, 2) if ret_2018 == ret_2018 else None,
        "return_2022_pct": round(ret_2022 * 100, 2) if ret_2022 == ret_2022 else None,
        "baseline_return_2018_pct": round(base_ret_2018 * 100, 2) if base_ret_2018 == base_ret_2018 else None,
        "baseline_return_2022_pct": round(base_ret_2022 * 100, 2) if base_ret_2022 == base_ret_2022 else None,
        "note": extra_turnover_note,
    }


# ---------------------------------------------------------------------------
# Signal builders -> each returns a weights_df (index=all TRAIN dates that are
# common to the idea's universe, columns=tickers incl. SHY, ffilled target
# weight AS OF that date's close -- lag+cost applied uniformly afterwards).
# ---------------------------------------------------------------------------

def mom_return(px, lookback_days, skip_days=0):
    if skip_days > 0:
        ref = px.shift(skip_days)
    else:
        ref = px
    return ref / ref.shift(lookback_days) - 1.0


def idea_abs_momentum(risky, cash, lookback_m, skip_m):
    uni = [risky, cash]
    dates = common_dates(uni)
    lb_days = lookback_m * 21
    skip_days = skip_m * 21
    px = ADJ_CLOSE[risky].loc[dates]
    mom = mom_return(px, lb_days, skip_days)
    sig_dates = month_end_signal_dates(dates)
    mom_at_sig = mom.reindex(sig_dates)

    w = pd.DataFrame(0.0, index=dates, columns=uni)
    target = pd.Series(index=sig_dates, dtype=object)
    for d in sig_dates:
        m = mom_at_sig.loc[d]
        if pd.isna(m):
            target.loc[d] = None
            continue
        target.loc[d] = {risky: 1.0, cash: 0.0} if m > 0 else {risky: 0.0, cash: 1.0}

    first_valid = target.dropna().index.min()
    for d in sig_dates:
        t = target.loc[d]
        if t is None:
            continue
        for k, v in t.items():
            w.loc[d:, k] = v
    return w.loc[dates], first_valid


def idea_dual_momentum(universe, cash, lookback_m, top_k):
    uni = universe + [cash]
    dates = common_dates(uni)
    lb_days = lookback_m * 21
    px = ADJ_CLOSE[universe].loc[dates]
    mom = px / px.shift(lb_days) - 1.0
    sig_dates = month_end_signal_dates(dates)
    mom_at_sig = mom.reindex(sig_dates)

    w = pd.DataFrame(0.0, index=dates, columns=uni)
    first_valid = None
    for d in sig_dates:
        row = mom_at_sig.loc[d]
        if row.isna().any():
            continue
        if first_valid is None:
            first_valid = d
        ranked = row.sort_values(ascending=False)
        picks = ranked.index[:top_k]
        alloc = {}
        for p in picks:
            alloc[p] = (1.0 / top_k) if row[p] > 0 else 0.0
        cash_w = 1.0 - sum(alloc.values())
        for k, v in alloc.items():
            w.loc[d:, k] = v
        w.loc[d:, cash] = cash_w
        for other in universe:
            if other not in alloc:
                w.loc[d:, other] = 0.0
    return w.loc[dates], first_valid


def idea_vol_adj_momentum(universe, cash, lookback_m, top_k):
    uni = universe + [cash]
    dates = common_dates(uni)
    lb_days = lookback_m * 21
    px = ADJ_CLOSE[universe].loc[dates]
    ret = px.pct_change()
    cum_ret = px / px.shift(lb_days) - 1.0
    vol = ret.rolling(lb_days).std()
    score = cum_ret / vol
    sig_dates = month_end_signal_dates(dates)
    score_at_sig = score.reindex(sig_dates)
    cumret_at_sig = cum_ret.reindex(sig_dates)

    w = pd.DataFrame(0.0, index=dates, columns=uni)
    first_valid = None
    for d in sig_dates:
        row = score_at_sig.loc[d]
        if row.isna().any():
            continue
        if first_valid is None:
            first_valid = d
        ranked = row.sort_values(ascending=False)
        picks = ranked.index[:top_k]
        alloc = {}
        for p in picks:
            alloc[p] = (1.0 / top_k) if cumret_at_sig.loc[d, p] > 0 else 0.0
        cash_w = 1.0 - sum(alloc.values())
        for k, v in alloc.items():
            w.loc[d:, k] = v
        w.loc[d:, cash] = cash_w
        for other in universe:
            if other not in alloc:
                w.loc[d:, other] = 0.0
    return w.loc[dates], first_valid


def idea_ma_filter(risky, cash, ma_window, check="daily"):
    uni = [risky, cash]
    dates = common_dates(uni)
    px = ADJ_CLOSE[risky].loc[dates]
    ma = px.rolling(ma_window).mean()
    state = (px > ma).astype(float)  # 1 = risky on

    if check == "month_end":
        sig_dates = month_end_signal_dates(dates)
        state = state.reindex(sig_dates)
        full = pd.Series(index=dates, dtype=float)
        full.loc[sig_dates] = state.values
        full = full.ffill()
        state = full

    first_valid = state.dropna().index.min()
    w = pd.DataFrame(0.0, index=dates, columns=uni)
    w[risky] = state.fillna(0.0)
    w[cash] = 1.0 - w[risky]
    return w, first_valid


def idea_abs_momentum_adx_gate(risky, cash, lookback_m, skip_m, adx_threshold=20.0):
    uni = [risky, cash]
    dates = common_dates(uni)
    lb_days = lookback_m * 21
    skip_days = skip_m * 21
    px = ADJ_CLOSE[risky].loc[dates]
    mom = mom_return(px, lb_days, skip_days)
    adx, _ = compute_adx14(risky)
    adx = adx.loc[dates]

    sig_dates = month_end_signal_dates(dates)
    mom_at_sig = mom.reindex(sig_dates)
    adx_at_sig = adx.reindex(sig_dates)

    w = pd.DataFrame(0.0, index=dates, columns=uni)
    first_valid = None
    for d in sig_dates:
        m, a = mom_at_sig.loc[d], adx_at_sig.loc[d]
        if pd.isna(m) or pd.isna(a):
            continue
        if first_valid is None:
            first_valid = d
        if a >= adx_threshold and m > 0:
            w.loc[d:, risky] = 1.0
            w.loc[d:, cash] = 0.0
        else:
            w.loc[d:, risky] = 0.0
            w.loc[d:, cash] = 1.0
    return w, first_valid


def idea_dual_momentum_trend_gate(universe, cash, lookback_m, top_k, ma_window=200, atr_gate=1.0):
    """Same as idea_dual_momentum, but at each monthly check, only rebalance if
    SPY's |price - 200dma| / ATR14 >= atr_gate; otherwise keep prior month's weights
    (reduces churn in weak-trend regimes)."""
    uni = universe + [cash]
    dates = common_dates(uni)
    lb_days = lookback_m * 21
    px = ADJ_CLOSE[universe].loc[dates]
    mom = px / px.shift(lb_days) - 1.0

    spy_px = ADJ_CLOSE["SPY"].loc[dates]
    spy_ma = spy_px.rolling(ma_window).mean()
    _, spy_atr = compute_adx14("SPY")
    spy_atr = spy_atr.loc[dates]
    trend_strength = (spy_px - spy_ma).abs() / spy_atr

    sig_dates = month_end_signal_dates(dates)
    mom_at_sig = mom.reindex(sig_dates)
    gate_at_sig = trend_strength.reindex(sig_dates)

    w = pd.DataFrame(0.0, index=dates, columns=uni)
    first_valid = None
    prev_alloc = None
    for d in sig_dates:
        row = mom_at_sig.loc[d]
        g = gate_at_sig.loc[d]
        if row.isna().any() or pd.isna(g):
            continue
        if first_valid is None:
            first_valid = d
        if g < atr_gate and prev_alloc is not None:
            alloc, cash_w = prev_alloc
        else:
            ranked = row.sort_values(ascending=False)
            picks = ranked.index[:top_k]
            alloc = {}
            for p in picks:
                alloc[p] = (1.0 / top_k) if row[p] > 0 else 0.0
            cash_w = 1.0 - sum(alloc.values())
            prev_alloc = (alloc, cash_w)
        for k, v in alloc.items():
            w.loc[d:, k] = v
        w.loc[d:, cash] = cash_w
        for other in universe:
            if other not in alloc:
                w.loc[d:, other] = 0.0
    return w, first_valid


# ---------------------------------------------------------------------------
# Run all 14 ideas
# ---------------------------------------------------------------------------

def run_idea(idea_id, family, weights_df, first_valid, uni_tickers, note=""):
    dates = weights_df.index
    eval_start = first_valid
    eval_end = dates.max()
    if eval_start is None or pd.isna(eval_start) or eval_start >= eval_end:
        return {"idea_id": idea_id, "family": family, "note": "insufficient_history"}

    ret_df = ADJ_CLOSE[uni_tickers].loc[dates].pct_change()
    net_ret, n_rebalances, _ = apply_lag_and_cost(weights_df, ret_df, eval_start, eval_end)
    baseline_ret = spy_baseline(eval_start, eval_end)
    # align indices exactly (both already restricted to [eval_start, eval_end] on their own calendars)
    common_idx = net_ret.index.intersection(baseline_ret.index)
    net_ret = net_ret.loc[common_idx]
    baseline_ret = baseline_ret.loc[common_idx]

    return summarize(idea_id, family, net_ret, n_rebalances, common_idx.min(), common_idx.max(), baseline_ret, note)


def main():
    results = []

    # EM01 / EM02: absolute momentum SPY on/off
    w, fv = idea_abs_momentum("SPY", "SHY", 12, 1)
    results.append(run_idea("EM01", "abs_momentum", w, fv, ["SPY", "SHY"]))
    w, fv = idea_abs_momentum("SPY", "SHY", 6, 1)
    results.append(run_idea("EM02", "abs_momentum", w, fv, ["SPY", "SHY"]))

    # EM03 / EM05: dual momentum top1, 12m and 6m
    dm_universe = ["SPY", "QQQ", "IWM", "EFA", "EEM", "TLT", "GLD"]
    w, fv = idea_dual_momentum(dm_universe, "SHY", 12, 1)
    results.append(run_idea("EM03", "dual_momentum", w, fv, dm_universe + ["SHY"]))
    w, fv = idea_dual_momentum(dm_universe, "SHY", 6, 1)
    results.append(run_idea("EM05", "dual_momentum", w, fv, dm_universe + ["SHY"]))

    # EM04: dual momentum top3, 6m
    w, fv = idea_dual_momentum(dm_universe, "SHY", 6, 3)
    results.append(run_idea("EM04", "dual_momentum", w, fv, dm_universe + ["SHY"]))

    # EM06 / EM07: 200dma filter, daily check vs month-end check
    w, fv = idea_ma_filter("SPY", "SHY", 200, check="daily")
    results.append(run_idea("EM06", "ma_filter", w, fv, ["SPY", "SHY"]))
    w, fv = idea_ma_filter("SPY", "SHY", 200, check="month_end")
    results.append(run_idea("EM07", "ma_filter", w, fv, ["SPY", "SHY"]))

    # EM08 / EM09 / EM10: sector rotation
    sectors = ["XLE", "XLF", "XLK", "XLV", "XLY", "XLP"]
    w, fv = idea_dual_momentum(sectors, "SHY", 6, 2)
    results.append(run_idea("EM08", "sector_rotation", w, fv, sectors + ["SHY"]))
    w, fv = idea_dual_momentum(sectors, "SHY", 6, 3)
    results.append(run_idea("EM09", "sector_rotation", w, fv, sectors + ["SHY"]))
    w, fv = idea_dual_momentum(sectors, "SHY", 12, 2)
    results.append(run_idea("EM10", "sector_rotation", w, fv, sectors + ["SHY"]))

    # EM11 / EM12: vol-adjusted momentum
    w, fv = idea_vol_adj_momentum(dm_universe, "SHY", 6, 1)
    results.append(run_idea("EM11", "vol_adjusted_momentum", w, fv, dm_universe + ["SHY"]))
    w, fv = idea_vol_adj_momentum(dm_universe, "SHY", 6, 3)
    results.append(run_idea("EM12", "vol_adjusted_momentum", w, fv, dm_universe + ["SHY"]))

    # EM13: abs momentum + ADX gate
    w, fv = idea_abs_momentum_adx_gate("SPY", "SHY", 12, 1, adx_threshold=20.0)
    results.append(run_idea("EM13", "trend_strength_filter", w, fv, ["SPY", "SHY"]))

    # EM14: dual momentum top1 12m + trend-strength gate (skip rebalance if weak trend)
    w, fv = idea_dual_momentum_trend_gate(dm_universe, "SHY", 12, 1, ma_window=200, atr_gate=1.0)
    results.append(run_idea("EM14", "trend_strength_filter", w, fv, dm_universe + ["SHY"]))

    df = pd.DataFrame(results)
    df.to_csv(f"{OUT_DIR}/RESULTS.csv", index=False)
    print(df.to_string(index=False))


if __name__ == "__main__":
    main()
