#!/usr/bin/env python3
# EXPLORATORY SCREEN ONLY - no TRAIN_TRIALS.csv writes; train rows strictly before 2026-06-01.
"""Train-only exploratory ETF screen with next-session-open execution."""
from __future__ import annotations

import csv
import os
from bisect import bisect_left
from datetime import date, datetime
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.dataset as ds

HERE = Path(__file__).resolve().parent
CUTOFF = date(2026, 6, 1)
COST = 0.0006
ETF_REL = "external/equities/us/yahoo_daily_us_etf.parquet"
FRED_REL = "external/equities/macro/fred_series.parquet"
TICKERS = ["SPY", "QQQ", "SCHD", "VYM", "DVY", "SHY"]


def iso(value):
    return value.date().isoformat() if isinstance(value, datetime) else value.isoformat()


def read_data():
    root = Path(os.environ["TRADING_DATA_DIR"])
    cutoff = pa.scalar(datetime(2026, 6, 1), type=pa.timestamp("ns"))
    prices_ds = ds.dataset(root / ETF_REL, format="parquet")
    # The strict less-than filter is mandatory: no test row is read or processed.
    prices = prices_ds.to_table(
        filter=(ds.field("date") < cutoff) & ds.field("ticker").isin(TICKERS),
        columns=["ticker", "date", "open", "high", "low", "close", "adj_close"],
    ).to_pylist()
    if not prices:
        raise RuntimeError("No train ETF rows loaded")
    by_ticker = {t: {} for t in TICKERS}
    for r in prices:
        d = iso(r["date"])
        assert date.fromisoformat(d) < CUTOFF, f"Cutoff violation in ETF rows: {d}"
        by_ticker[r["ticker"]][d] = r
    fred_ds = ds.dataset(root / FRED_REL, format="parquet")
    fred = fred_ds.to_table(
        filter=(ds.field("series") == "DGS10") & (ds.field("date") < cutoff),
        columns=["date", "value"],
    ).to_pylist()
    yields = {}
    for r in fred:
        d = iso(r["date"])
        assert date.fromisoformat(d) < CUTOFF, f"Cutoff violation in FRED rows: {d}"
        if r["value"] is not None:
            yields[d] = float(r["value"])
    if not yields:
        raise RuntimeError("No train DGS10 observations")
    return by_ticker, yields


def frame_for(tickers, data):
    common = set(data[tickers[0]])
    for ticker in tickers[1:]:
        common.intersection_update(data[ticker])
    dates = sorted(common)
    if len(dates) < 300:
        raise RuntimeError(f"Insufficient common sessions for {tickers}: {len(dates)}")
    out = {"date": dates}
    for ticker in tickers:
        out[ticker] = {}
        out[ticker + "_adj"] = {}
        for d in dates:
            r = data[ticker][d]
            if any(r[k] is None for k in ("open", "close", "adj_close")) or r["close"] == 0:
                raise RuntimeError(f"Bad OHLC input: {ticker} {d}")
            out[ticker][d] = float(r["open"]) * float(r["adj_close"]) / float(r["close"])
            out[ticker + "_adj"][d] = float(r["adj_close"])
    return out


def signal_value(frame, signal_i, spec, yields, yield_dates):
    dates = frame["date"]
    d = dates[signal_i]
    kind = spec["kind"]
    if kind == "relative":
        a, b, window = spec["a"], spec["b"], spec["window"]
        if signal_i < window:
            return b
        ra = frame[a + "_adj"][d] / frame[a + "_adj"][dates[signal_i - window]] - 1
        rb = frame[b + "_adj"][d] / frame[b + "_adj"][dates[signal_i - window]] - 1
        return a if ra > rb else b
    if kind == "rate":
        a, b, window = spec["a"], spec["b"], spec["window"]
        if signal_i < window:
            return b
        ra = frame[a + "_adj"][d] / frame[a + "_adj"][dates[signal_i - window]] - 1
        rb = frame[b + "_adj"][d] / frame[b + "_adj"][dates[signal_i - window]] - 1
        f = bisect_left(yield_dates, d) - 1  # strictly before signal session, per precedent
        earlier_date = dates[max(0, signal_i - spec["rate_window"])]
        earlier = bisect_left(yield_dates, earlier_date) - 1
        falling = f >= 0 and earlier >= 0 and yields[yield_dates[f]] < yields[yield_dates[earlier]]
        return a if ra > rb and falling else b
    if kind == "tom" or kind == "may":
        ex_d = dates[signal_i + 1]
        ex = date.fromisoformat(ex_d)
        if kind == "may":
            return "SPY" if ex.month in (11, 12, 1, 2, 3, 4) else "SHY"
        n = spec["n"]
        month = ex.month
        month_dates = [date.fromisoformat(x) for x in dates]
        current = [x for x in month_dates if x.year == ex.year and x.month == month]
        prior_month = 12 if month == 1 else month - 1
        prior_year = ex.year - 1 if month == 1 else ex.year
        prior = [x for x in month_dates if x.year == prior_year and x.month == prior_month]
        use = ex in current[:n] or ex in prior[-n:]
        return "SPY" if use else "SHY"
    if kind == "dip":
        if signal_i < spec["window"]:
            return "SHY"
        past_d = dates[signal_i - spec["window"]]
        draw = frame["SPY_adj"][d] / frame["SPY_adj"][past_d] - 1
        # Hold M execution sessions after a qualifying signal; repeated signals refresh expiry.
        recent_signal = any(
            frame["SPY_adj"][dates[j]] / frame["SPY_adj"][dates[j - spec["window"]]] - 1 <= -spec["drop"]
            for j in range(max(spec["window"], signal_i - spec["hold"] + 1), signal_i + 1)
        )
        return "SPY" if draw <= -spec["drop"] or recent_signal else "SHY"
    if kind == "ma":
        if signal_i < 199:
            return "SHY"
        vals = [frame["SPY_adj"][dates[j]] for j in range(signal_i - 199, signal_i + 1)]
        return "SPY" if frame["SPY_adj"][d] / (sum(vals) / len(vals)) - 1 <= -spec["drop"] else "SHY"
    raise ValueError(f"Unknown signal kind {kind}")


IDEAS = [
    ("D001", "SCHD_vs_QQQ_126d", {"kind":"relative","a":"SCHD","b":"QQQ","window":126}, ["SCHD","QQQ"]),
    ("D002", "VYM_vs_SPY_126d", {"kind":"relative","a":"VYM","b":"SPY","window":126}, ["VYM","SPY"]),
    ("D003", "DVY_vs_SPY_252d", {"kind":"relative","a":"DVY","b":"SPY","window":252}, ["DVY","SPY"]),
    ("D004", "SCHD_rate_gate", {"kind":"rate","a":"SCHD","b":"SPY","window":126,"rate_window":63}, ["SCHD","SPY"]),
    ("D005", "VYM_rate_gate", {"kind":"rate","a":"VYM","b":"SPY","window":126,"rate_window":126}, ["VYM","SPY"]),
    ("D006", "TOM_1", {"kind":"tom","n":3}, ["SPY","SHY"]),
    ("D007", "TOM_3", {"kind":"tom","n":5}, ["SPY","SHY"]),
    ("D008", "Sell_May", {"kind":"may"}, ["SPY","SHY"]),
    ("D009", "Dip10_5pct_hold5", {"kind":"dip","window":10,"drop":.05,"hold":5}, ["SPY","SHY"]),
    ("D010", "Dip10_7pct_hold10", {"kind":"dip","window":10,"drop":.07,"hold":10}, ["SPY","SHY"]),
    ("D011", "Dip20_8pct_hold10", {"kind":"dip","window":20,"drop":.08,"hold":10}, ["SPY","SHY"]),
    ("D012", "Anti200DMA_10pct", {"kind":"ma","drop":.10}, ["SPY","SHY"]),
    ("D013", "Anti200DMA_15pct", {"kind":"ma","drop":.15}, ["SPY","SHY"]),
    ("D014", "Anti200DMA_20pct", {"kind":"ma","drop":.20}, ["SPY","SHY"]),
]


def simulate(f, yields, yield_dates, spec):
    dates = f["date"]
    start_signal = max(0, 1)
    held = ""
    nav = 1.0
    curve = []
    daily_returns = []
    switches = 0
    transitions = []
    for exec_i in range(start_signal, len(dates) - 1):
        pretrade_nav = nav
        sig_i = exec_i - 1
        target = signal_value(f, sig_i, spec, yields, yield_dates)
        sig_date, exec_date = dates[sig_i], dates[exec_i]
        assert sig_date < exec_date, f"Look-ahead execution ordering failed: {sig_date} >= {exec_date}"
        if target != held:
            turnover = (1.0 if held else 0.0) + (1.0 if target else 0.0)
            nav *= 1.0 - COST * turnover
            switches += 1
            transitions.append((sig_date, exec_date))
            held = target
        nav *= f[held][dates[exec_i + 1]] / f[held][exec_date]
        daily_returns.append((exec_date[:4], nav / pretrade_nav))
        curve.append((exec_date, nav))
    if held:
        nav *= 1.0 - COST
        switches += 1
        assert dates[-2] < dates[-1], "Final exit must execute after its signal session"
        daily_returns.append((dates[-1][:4], 1.0 - COST))
        curve.append((dates[-1], nav))
    for sig_date, exec_date in transitions:
        assert sig_date < exec_date
    assert all(date.fromisoformat(d) < CUTOFF for d in dates)
    yearly = {}
    for year, factor in daily_returns:
        yearly[year] = yearly.get(year, 1.0) * factor
    peak, mdd = 1.0, 0.0
    for _, value in curve:
        peak = max(peak, value)
        mdd = min(mdd, value / peak - 1.0)
    total = nav - 1.0
    span_years = max((len(dates) - start_signal - 1) / 252.0, 1 / 252.0)
    return {"total":total,"mdd":mdd,"switches":switches,"switch_per_year":switches/span_years,
            "yearly":yearly,"start":dates[start_signal],"end":dates[-1],"nav":nav}


def causality_test(data):
    ticker = "SPY"
    dates = sorted(data[ticker])
    cut_i = min(120, len(dates) - 5)
    chosen = dates[cut_i]
    original = [(d, data[ticker][d]["adj_close"]) for d in dates]
    mutated_rows = {d: dict(data[ticker][d]) for d in dates}
    for d in dates:
        if d >= chosen:
            for field in ("open", "high", "low", "close", "adj_close"):
                mutated_rows[d][field] = 0.0
    mutated = [(d, mutated_rows[d]["adj_close"]) for d in dates]
    def prior_momentum(values, at):
        lookup = dict(values)
        i = dates.index(at)
        if i < 20:
            return None
        return lookup[dates[i]] / lookup[dates[i - 20]] - 1
    checked = dates[max(20, cut_i - 20):cut_i]
    assert all(prior_momentum(original, d) == prior_momentum(mutated, d) for d in checked)
    return True, chosen, len(checked)


def main():
    data, yields = read_data()
    yield_dates = sorted(yields)
    passed, chosen, checked = causality_test(data)
    print(f"CAUSALITY SELF-TEST: {'PASS' if passed else 'FAIL'} (future OHLC/adjusted values zeroed from {chosen}; {checked} prior signals unchanged)")
    results = []
    for idea_id, name, spec, assets in IDEAS:
        frame = frame_for(assets, data)
        m = simulate(frame, yields, yield_dates, spec)
        # The benchmark is SPY buy-and-hold over the exact strategy window, with same initial/final costs.
        # Build its return directly from the adjusted-open series.
        spy_open = frame_for(["SPY"], data)
        spy_dates = spy_open["date"]
        aligned = [d for d in spy_dates if m["start"] <= d <= m["end"]]
        spy_nav = (1.0 - COST) * (spy_open["SPY"][aligned[-1]] / spy_open["SPY"][aligned[0]]) * (1.0 - COST)
        spy_total = spy_nav - 1.0
        spy_curve = [(1.0 - COST) * spy_open["SPY"][d] / spy_open["SPY"][aligned[0]] for d in aligned]
        spy_curve[-1] *= 1.0 - COST
        spy_peak, spy_mdd = 1.0, 0.0
        for v in spy_curve:
            spy_peak = max(spy_peak, v)
            spy_mdd = min(spy_mdd, v / spy_peak - 1)
        results.append({"idea_id":idea_id,"name":name,"trade_count":m["switches"],
            "switches_per_year":m["switch_per_year"],"total_return":m["total"],"mdd":m["mdd"],
            "excess_vs_spy":m["total"]-spy_total,"mdd_diff_vs_spy":m["mdd"]-spy_mdd,
            "return_2018":m["yearly"].get("2018",float("nan"))-1,
            "return_2022":m["yearly"].get("2022",float("nan"))-1,
            "spy_buy_hold_return":spy_total,"spy_buy_hold_mdd":spy_mdd,
            "start_date":m["start"],"end_date":m["end"],"_yearly":m["yearly"]})
    years = sorted(set(y for r in results for y in r["_yearly"]) | {"2018", "2022"})
    for r in results:
        yearly = r.pop("_yearly")
        for year in years:
            r[f"return_{year}"] = yearly.get(year, float("nan")) - 1
    fields = list(results[0])
    with (HERE / "RESULTS.csv").open("w", newline="", encoding="utf-8") as h:
        w = csv.DictWriter(h, fieldnames=fields); w.writeheader(); w.writerows(results)
    ranked = sorted(results, key=lambda x:(x["excess_vs_spy"], x["mdd"]), reverse=True)
    lines = ["# RANKED TOP 10 - EXPLORATORY SCREEN ONLY", "", "Ranking formula: excess total return over SPY buy-and-hold on each idea's matching date window; ties favor smaller drawdown (less negative MDD). This is a descriptive screen, not an inferential score.", "", "| rank | idea_id | name | excess vs SPY | total return | MDD | switches/year |", "|---:|---|---|---:|---:|---:|---:|"]
    for rank, r in enumerate(ranked[:10], 1):
        lines.append(f"| {rank} | {r['idea_id']} | {r['name']} | {r['excess_vs_spy']:.2%} | {r['total_return']:.2%} | {r['mdd']:.2%} | {r['switches_per_year']:.2f} |")
    lines += ["", "## Why-notes", ""]
    for rank, r in enumerate(ranked[:10], 1):
        idea = next(x for x in IDEAS if x[0] == r["idea_id"])
        lines.append(f"{rank}. **{r['name']}**: screened for its stated {idea[2]['kind']} mechanism; observed ranking is based only on train-window excess return and drawdown.")
    lines += ["", "## Caveats", "", "- EXPLORATORY SCREEN ONLY; no preregistration, no multiple-testing correction, and no promotion without separate formal preregistration and full validation.", "- All parquet queries filter strictly to dates before 2026-06-01; no test rows are read. Results are train-only and selected from 14 variants.", "- Daily adjusted-open sequential portfolio approximation; 6 bp one-way turnover cost, charged on initial entry, allocation changes by L1 turnover, and final exit. A direct switch between fully invested ETFs incurs 12 bp.", "- Each rotation starts on the first common listed session; no missing history is backfilled or interpolated. SPY buy-and-hold comparison uses the same date window and entry/exit cost.", "- Synthetic causality self-test checks that future OHLC-derived values zeroed from a cutoff do not alter earlier 20-session momentum values. Every actual rebalance asserts signal_date < execution_date.", "- No walk-forward selection, random-entry null, multiplicity correction, cost stress, or prospective paper test was performed.", ""]
    (HERE / "RANKED_TOP10.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"WROTE {len(results)} ideas to RESULTS.csv; {len(ranked[:10])} ranked in RANKED_TOP10.md")
    for r in ranked:
        print(f"{r['idea_id']} {r['name']} total={r['total_return']:.2%} excess={r['excess_vs_spy']:.2%} MDD={r['mdd']:.2%} switches={r['trade_count']}")


if __name__ == "__main__":
    main()
