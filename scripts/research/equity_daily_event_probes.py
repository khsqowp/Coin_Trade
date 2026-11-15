#!/usr/bin/env python3
"""Development-only KR stock breakout event study and delayed US SPY gap-fade probe.

Reads only daily CSV rows strictly before the exclusive cutoff. This is not a
portfolio sizing recommendation or autonomous-trading readiness test.
"""
import argparse
import csv
from collections import defaultdict
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

CACHE = Path(__file__).resolve().parents[2] / ".kis-cache-local"
CUTOFF = pd.Timestamp("2024-11-12T00:00:00Z")
KR_ETFS = {
    "069500", "091160", "091170", "091180", "102110", "102970", "114260", "114800",
    "117460", "117680", "117700", "132030", "133690", "139230", "139260", "140700",
    "140710", "143860", "148070", "153130", "157490", "229200", "244580", "261240",
    "305720", "307950",
}
KR_COMM = 0.00015
KR_TAX = 0.0018
KR_SLIP_BASE = 0.0010
KR_SLIP_STRESS = 0.0020
US_COST_BASE = 0.0036
US_COST_STRESS = 0.0122


def load_pre_cutoff(path):
    rows = []
    with path.open(encoding="utf-8") as stream:
        header = next(stream).strip().split(",")
        col = {name: i for i, name in enumerate(header)}
        previous = None
        for line in stream:
            stamp_text = line.partition(",")[0]
            stamp = pd.Timestamp(stamp_text)
            if stamp >= CUTOFF:
                break  # Only the timestamp is parsed on/after the exclusive cutoff.
            if previous is not None and stamp <= previous:
                raise ValueError(f"non-monotonic timestamp before cutoff: {path}")
            previous = stamp
            fields = line.rstrip("\r\n").split(",")
            rows.append((stamp, *(float(fields[col[key]]) for key in ("Open", "High", "Low", "Close", "Volume"))))
    return rows


def next_month(year_month):
    year, month = map(int, year_month.split("-"))
    return f"{year + (month == 12):04d}-{1 if month == 12 else month + 1:02d}"


def net_long_return(entry, exit_price, slip):
    buy_cost = KR_COMM + slip
    sell_cost = KR_COMM + KR_TAX + slip
    return (exit_price / entry) * (1 - sell_cost) / (1 + buy_cost) - 1


def kr_events(symbol, rows, require_volume):
    if len(rows) < 25:
        return []
    stamps = [row[0] for row in rows]
    opens = np.asarray([row[1] for row in rows])
    closes = np.asarray([row[4] for row in rows])
    volumes = np.asarray([row[5] for row in rows])
    month_ends = {}
    for i, stamp in enumerate(stamps):
        month_ends[stamp.strftime("%Y-%m")] = i
    results = []
    previous_exit = -1
    for i in range(21, len(rows) - 1):
        prior_max_close = float(np.max(closes[i - 20:i]))
        prior_median_volume = float(np.median(volumes[i - 20:i]))
        if not (closes[i] > prior_max_close and closes[i - 1] <= np.max(closes[i - 21:i - 1])):
            continue
        volume_ratio = volumes[i] / prior_median_volume if prior_median_volume > 0 else np.nan
        if require_volume and (not np.isfinite(volume_ratio) or volume_ratio < 1.5):
            continue
        entry_i = i + 1
        exit_i = month_ends.get(next_month(stamps[i].strftime("%Y-%m")))
        if exit_i is None or exit_i <= entry_i or entry_i <= previous_exit:
            continue
        entry, exit_price = opens[entry_i], opens[exit_i]
        if not (np.isfinite(entry) and np.isfinite(exit_price) and entry > 0 and exit_price > 0):
            continue
        results.append({
            "market": "KR", "symbol": symbol,
            "signal_date": stamps[i].date().isoformat(),
            "entry_date": stamps[entry_i].date().isoformat(),
            "exit_date": stamps[exit_i].date().isoformat(),
            "volume_confirmed": int(require_volume), "volume_ratio": volume_ratio,
            "gross_return_pct": (exit_price / entry - 1) * 100,
            "net_base_pct": net_long_return(entry, exit_price, KR_SLIP_BASE) * 100,
            "net_stress_pct": net_long_return(entry, exit_price, KR_SLIP_STRESS) * 100,
        })
        previous_exit = exit_i
    return results


def bootstrap_mean(values, dates, seed):
    if len(values) == 0:
        return (float("nan"), float("nan"))
    unique = np.asarray(sorted(set(dates)))
    groups = {day: np.asarray([i for i, value in enumerate(dates) if value == day]) for day in unique}
    rng = np.random.default_rng(seed)
    means = np.empty(2000)
    for draw_i in range(len(means)):
        sample_days = rng.choice(unique, len(unique), replace=True)
        ix = np.concatenate([groups[day] for day in sample_days])
        means[draw_i] = np.mean(values[ix])
    return tuple(np.quantile(means, [0.025, 0.975]))


def summarize_kr(events):
    out = []
    for confirmed in (0, 1):
        sample = [e for e in events if e["volume_confirmed"] == confirmed]
        for cost in ("base", "stress"):
            values = np.asarray([e[f"net_{cost}_pct"] for e in sample], dtype=float)
            dates = [e["signal_date"] for e in sample]
            out.append({
                "market": "KR", "strategy": "20d_close_breakout_volume_1.5x" if confirmed else "20d_close_breakout_no_volume",
                "cost_case": cost, "trades": len(sample),
                "positive_rate": float(np.mean(values > 0)) if len(values) else float("nan"),
                "mean_net_pct": float(np.mean(values)) if len(values) else float("nan"),
                "median_net_pct": float(np.median(values)) if len(values) else float("nan"),
                "mean_net_month_cluster95_pct": bootstrap_mean(values, [day[:7] for day in dates], 309 + confirmed + (cost == "stress")),
                "first_signal": min(dates) if dates else "", "last_signal": max(dates) if dates else "",
                "portfolio_cagr_mdd": "not computed: no user-approved position sizing/overlap policy",
            })
    return out


def us_gap_fade(rows):
    stamps = [row[0] for row in rows]
    opens = np.asarray([row[1] for row in rows])
    closes = np.asarray([row[4] for row in rows])
    events = []
    for i in range(1, len(rows) - 1):
        gap = opens[i] / closes[i - 1] - 1 if closes[i - 1] > 0 else 0.0
        side = -1 if gap >= 0.005 else (1 if gap <= -0.005 else 0)
        if side:
            trade_i = i + 1  # Gap is known only at today's opening print; enter next session.
            raw = side * (closes[trade_i] / opens[trade_i] - 1)
            reverse_raw = -raw
            events.append({
                "market": "US", "symbol": "SPY", "signal_date": stamps[i].date().isoformat(),
                "entry_date": stamps[trade_i].date().isoformat(), "exit_date": stamps[trade_i].date().isoformat(),
                "gap_pct": gap * 100, "side": "short" if side < 0 else "long",
                "gross_return_pct": raw * 100,
                "net_base_pct": (raw - US_COST_BASE) * 100,
                "net_stress_pct": (raw - US_COST_STRESS) * 100,
                "reverse_net_base_pct": (reverse_raw - US_COST_BASE) * 100,
                "reverse_net_stress_pct": (reverse_raw - US_COST_STRESS) * 100,
            })
    rows_out = []
    n_sessions = max(1, len(rows) - 2)
    for family, field_prefix in (("delayed_1d_gap_fade", "net"), ("matched_reverse_side", "reverse_net")):
        for cost_case in ("base", "stress"):
            values = np.asarray([e[f"{field_prefix}_{cost_case}_pct"] for e in events], dtype=float)
            dates = [e["signal_date"] for e in events]
            rows_out.append({
                "market": "US", "strategy": family, "cost_case": cost_case,
                "trades": len(events), "signal_session_coverage_pct": len(events) / n_sessions * 100,
                "positive_rate": float(np.mean(values > 0)) if len(values) else float("nan"),
                "mean_net_per_trade_pct": float(np.mean(values)) if len(values) else float("nan"),
                "median_net_per_trade_pct": float(np.median(values)) if len(values) else float("nan"),
                "mean_net_month_cluster95_pct": bootstrap_mean(values, [day[:7] for day in dates], 511 + (field_prefix == "reverse_net") + (cost_case == "stress")),
                "portfolio_cagr_mdd": "not computed: event study only; account sizing is unapproved",
                "baseline": "same signal dates with opposite side; not an unconditional market baseline",
            })
    years = (stamps[-1] - stamps[2]).days / 365.2425 if len(stamps) > 3 else np.nan
    for label, round_trip_cost in (("base", US_COST_BASE), ("stress", US_COST_STRESS)):
        one_way = round_trip_cost / 2
        buyhold = closes[2:] / opens[2] / (1 + one_way)
        nav = np.r_[1.0, buyhold]
        nav[-1] *= 1 - one_way
        peak = np.maximum.accumulate(nav)
        rows_out.append({
            "market": "US", "strategy": "SPY_buy_and_hold", "cost_case": label,
            "trades": 1, "signal_session_coverage_pct": 100.0,
            "cagr_pct": float((nav[-1] ** (1 / years) - 1) * 100) if years > 0 and nav[-1] > 0 else float("nan"),
            "mdd_pct": float(np.max(1 - nav / peak) * 100),
            "mean_net_per_trade_pct": float((nav[-1] - 1) * 100),
            "baseline": "matching round-trip cost; entry at first evaluated open and terminal liquidation",
        })
    rows_out.append({
        "market": "US", "strategy": "cash", "cost_case": "both",
        "trades": 0, "signal_session_coverage_pct": 0.0, "cagr_pct": 0.0, "mdd_pct": 0.0,
        "mean_net_per_trade_pct": 0.0, "baseline": "zero-return cash",
    })
    return events, rows_out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    kr_paths = sorted(CACHE.glob("KR_*.csv"))
    kr_events_all = []
    for path in kr_paths:
        symbol = path.stem[3:]
        if symbol in KR_ETFS:
            continue
        kr_events_all.extend(kr_events(symbol, load_pre_cutoff(path), False))
        kr_events_all.extend(kr_events(symbol, load_pre_cutoff(path), True))
    spy_path = CACHE / "US_SPY.csv"
    spy_rows = load_pre_cutoff(spy_path)
    us_trades, us_summary = us_gap_fade(spy_rows)
    stock_count = sum(path.stem[3:] not in KR_ETFS for path in kr_paths)
    summaries = summarize_kr(kr_events_all) + us_summary
    for name, rows in (("kr_breakout_events.csv", kr_events_all), ("us_gap_fade_events.csv", us_trades),
                       ("summary.csv", summaries)):
        if rows:
            with (args.output_dir / name).open("w", newline="", encoding="utf-8") as stream:
                fields = list(dict.fromkeys(key for row in rows for key in row))
                writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
                writer.writeheader()
                writer.writerows(rows)
    print(f"KR files={len(kr_paths)} eligible_stock_files={stock_count} event_rows={len(kr_events_all)}")
    print(f"US SPY pre-cutoff rows={len(spy_rows)} events={len(us_trades)}")
    for row in summaries:
        print(row)


if __name__ == "__main__":
    main()
