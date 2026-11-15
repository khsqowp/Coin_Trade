"""Run the frozen MTF protocol on a previously explored development slice.

This command is descriptive only. It cannot produce validation/OOS claims.
The caller supplies database, universe, and report paths explicitly.
"""
import argparse
import hashlib
import json
import sqlite3
from collections import defaultdict
from pathlib import Path

import pandas as pd

from chart_predictor.mtf_consensus import TIMEFRAME_MINUTES, build_consensus, score_forecast
from chart_predictor.resample import resample_frame
from chart_predictor.setups import generate_signals

START_MS = 1784246400000
CUTOFF_MS = 1791504000000
SETUPS = ("bb_squeeze_breakout", "orb_funding_session", "vwap_band_fade",
          "volume_climax_exhaustion")
TIMEFRAMES = tuple(TIMEFRAME_MINUTES)
WIDTH_MS = {tf: minutes * 60_000 for tf, minutes in TIMEFRAME_MINUTES.items()}
MAX_HORIZON_BARS = 20


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def wilson_interval(successes, trials, z=1.959963984540054):
    if trials <= 0:
        return None, None
    p = successes / trials
    denominator = 1 + z * z / trials
    center = (p + z * z / (2 * trials)) / denominator
    radius = z * (p * (1 - p) / trials + z * z / (4 * trials * trials)) ** 0.5 / denominator
    return center - radius, center + radius


def summarize_confidence_slices(exact, symbols_by_exact):
    """Aggregate post-hoc vote-count thresholds; Wilson is intentionally naive."""
    cells = defaultdict(lambda: {"events": 0})
    for (timeframe, side, bars, votes), values in exact.items():
        cells[(timeframe, side, bars)]["events"] += values["events"]
    rows = []
    for timeframe, side, bars in sorted(cells, key=lambda key: (WIDTH_MS[key[0]], key[1], key[2])):
        denominator = cells[(timeframe, side, bars)]["events"]
        for threshold in range(2, len(TIMEFRAMES) + 1):
            totals = defaultdict(float)
            symbol_counts = defaultdict(int)
            for (tf, direction, horizon, votes), values in exact.items():
                if (tf, direction, horizon) != (timeframe, side, bars) or votes < threshold:
                    continue
                for name in ("events", "target", "stop", "timeout", "unscorable", "sum_net_r"):
                    totals[name] += values[name]
                for symbol, count in symbols_by_exact[(tf, direction, horizon, votes)].items():
                    symbol_counts[symbol] += count
            if not totals["events"]:
                continue
            scored = totals["target"] + totals["stop"] + totals["timeout"]
            lower, upper = wilson_interval(int(totals["target"]), int(scored))
            total_by_symbol = sum(symbol_counts.values())
            rows.append({
                "timeframe": timeframe, "side": side, "horizon_bars": bars,
                "min_votes": threshold, "events": int(totals["events"]),
                "coverage": totals["events"] / denominator if denominator else 0.0,
                "target": int(totals["target"]), "stop": int(totals["stop"]),
                "timeout": int(totals["timeout"]), "unscorable": int(totals["unscorable"]),
                "target_first_precision": totals["target"] / scored if scored else None,
                "wilson_lower_naive": lower, "wilson_upper_naive": upper,
                "symbols": len(symbol_counts),
                "largest_symbol_share": max(symbol_counts.values(), default=0) / total_by_symbol
                    if total_by_symbol else 0.0,
                "mean_net_r": totals["sum_net_r"] / scored if scored else None,
            })
    return rows


def render_markdown(report):
    lines = [
        "# Crypto MTF development exploration (not validation)", "",
        "This is a descriptive replay of a previously explored development interval. It is not a sealed holdout, out-of-sample result, or evidence that the 80% precision target is met.", "",
        "## Frozen run details", "",
        f"- Interval: `{report['start_utc']}` to exclusive `{report['cutoff_utc']}` (UTC).",
        f"- Symbols: {len(report['symbols'])}; timeframe widths: {', '.join(report['timeframes'])}.",
        f"- Base setups: {', '.join(report['setups'])}.",
        f"- Signal close then next 1m open; at least two fresh timeframe votes must agree; each timeframe has its own structure stop, fixed 2R target, 10/20-bar checkpoint; same-minute barrier ties are stop-first.",
        f"- Fee: {report['fee_round_trip']:.2%} round trip; no slippage, depth, or fillability model.",
        f"- Forecast rows (one row per emitted timeframe forecast): {report['forecast_rows']:,}.",
        f"- Candle DB SHA-256: `{report['input']['database_sha256']}`.",
        f"- Universe JSON SHA-256: `{report['input']['universe_sha256']}`.",
        "- The universe is the current collection list, not point-in-time membership. Delisted symbols and historical eligibility are not represented.",
        "", "## Unleveraged outcomes", "",
        "Precision is target-first count divided by target + stop + timeout; timeout is a non-hit. Mean net R is calculated per emitted forecast after the frozen round-trip fee, with the fixed 2R target. Each 10/20-bar row scores the same forecast cohort at a different deadline.", "",
        "|TF|Side|Horizon|N|Target|Stop|Timeout|Unscorable|Target-first|Mean net R|",
        "|---:|:---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in report["outcomes"]:
        precision = "—" if row["target_first_precision"] is None else f"{row['target_first_precision']:.2%}"
        mean_r = "—" if row["mean_net_r"] is None else f"{row['mean_net_r']:.3f}"
        lines.append(f"|{row['timeframe']}|{row['side']}|{row['horizon_bars']}|{row['events']}|{row['target']}|{row['stop']}|{row['timeout']}|{row['unscorable']}|{precision}|{mean_r}|")
    lines.extend([
        "", "## Exploratory confidence-threshold slices", "",
        "Confidence is the number of distinct active timeframe votes (2–9), a raw ranking score rather than a calibrated probability. Coverage is retained forecasts divided by the q≥2 consensus cohort within the same timeframe/side cell. Wilson bounds are naive per-row intervals and ignore shared consensus events, symbols, and market days; they cannot satisfy the registered validation gate.", "",
        "|TF|Side|Horizon|Min votes|N|Coverage|Target|Stop|Timeout|Unscorable|Precision|Naive Wilson lower|Symbols|Largest-symbol share|Mean net R|",
        "|---:|:---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ])
    for row in report.get("confidence_slices", []):
        precision = "—" if row["target_first_precision"] is None else f"{row['target_first_precision']:.2%}"
        lower = "—" if row["wilson_lower_naive"] is None else f"{row['wilson_lower_naive']:.2%}"
        mean_r = "—" if row["mean_net_r"] is None else f"{row['mean_net_r']:.3f}"
        lines.append(f"|{row['timeframe']}|{row['side']}|{row['horizon_bars']}|{row['min_votes']}|{row['events']}|{row['coverage']:.2%}|{row['target']}|{row['stop']}|{row['timeout']}|{row['unscorable']}|{precision}|{lower}|{row['symbols']}|{row['largest_symbol_share']:.2%}|{mean_r}|")
    lines.extend([
        "", "## Approximate 4x/5x outcomes at the 20-bar deadline", "",
        "Liquidation is modeled with the scorer's fixed 0.5% maintenance buffer; it is not an exchange/account-specific liquidation quote. Precision treats liquidation as a non-target outcome. Mean net R is not comparable to unleveraged R because leverage scales P&L.", "",
        "|TF|Side|Lev|N|Target|Stop|Liquidation|Timeout|Unscorable|Target-first|Mean net R|",
        "|---:|:---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ])
    for row in report["leveraged_outcomes"]:
        if row["horizon_bars"] != 20:
            continue
        precision = "—" if row["target_first_precision"] is None else f"{row['target_first_precision']:.2%}"
        mean_r = "—" if row["mean_net_r"] is None else f"{row['mean_net_r']:.3f}"
        lines.append(f"|{row['timeframe']}|{row['side']}|{row['leverage']}x|{row['events']}|{row['target']}|{row['stop']}|{row['liquidation']}|{row['timeout']}|{row['unscorable']}|{precision}|{mean_r}|")
    lines.extend([
        "", "## Decision", "",
        "Unfiltered q≥2 forecasts did not approach the 80% target-first objective; the best unleveraged 20-bar cell was 240m long at 35.20% (201/571 targets; mean net R +0.134), selected post-hoc among 36 cells. The vote-count slices below are a separate post-hoc development diagnostic. Neither result is independent validation or suitable evidence for live/manual deployment.", "",
        "## Missing validation gates", "",
        *[f"- {lim}" for lim in report["limitations"]],
        "- Confidence-slice coverage is conditional on the q≥2 consensus cohort within each cell; coverage over all eligible decision times was not computed, so the registered 10% coverage threshold is not tested.",
        "- The registered directional/momentum and fixed-seed random baselines were not replayed; no clustered Wilson bounds or multiplicity adjustment was computed.",
        "- The 80% criterion is plainly missed on descriptive precision, but this is not a complete statistical verdict because the development data were previously viewed and the cohort is not point-in-time.",
        "", "## Reproduction", "",
        "Run `python -m chart_predictor.mtf_dev_experiment --db <read-only-db> --universe <symbol-json> --output <report.json> --symbol-limit 50` from the repository root. The command opens SQLite in read-only mode and writes only to the caller-selected output path.",
        "",
    ])
    return "\n".join(lines)


def run_experiment(db_path, universe_path, output_path, symbol_limit=50):
    db_path, universe_path = Path(db_path).resolve(), Path(universe_path).resolve()
    output_path = Path(output_path).resolve()
    symbols = json.loads(universe_path.read_text())[:symbol_limit]
    if not symbols or len(symbols) != len(set(symbols)):
        raise ValueError("universe must contain unique symbols")

    totals = defaultdict(lambda: {"events": 0, "target": 0, "stop": 0,
                                  "timeout": 0, "unscorable": 0, "sum_net_r": 0.0})
    leverage_totals = defaultdict(lambda: {"events": 0, "target": 0, "stop": 0,
                                           "liquidation": 0, "timeout": 0,
                                           "unscorable": 0, "sum_net_r": 0.0})
    confidence_totals = defaultdict(lambda: {"events": 0, "target": 0, "stop": 0,
                                             "timeout": 0, "unscorable": 0,
                                             "sum_net_r": 0.0})
    confidence_symbols = defaultdict(lambda: defaultdict(int))
    db = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        for symbol_index, symbol in enumerate(symbols, 1):
            raw = pd.read_sql_query(
                "SELECT t_open_ms,o,h,l,c,v,quote_v,trades FROM candles "
                "WHERE symbol=? AND t_open_ms>=? AND t_open_ms<? ORDER BY t_open_ms",
                db, params=(symbol, START_MS, CUTOFF_MS))
            raw = raw.sort_values("t_open_ms", kind="stable").drop_duplicates(
                "t_open_ms").reset_index(drop=True)
            if raw.empty:
                print(f"symbols {symbol_index}/{len(symbols)}: {symbol}; no rows", flush=True)
                continue
            raw_times = raw.t_open_ms.to_numpy(dtype="int64")
            minute_open = dict(zip(raw_times, raw.o.astype(float)))
            signals_by_entry = defaultdict(list)
            for timeframe in TIMEFRAMES:
                frame = raw.copy() if timeframe == "1m" else resample_frame(
                    raw, timeframe, now_ms=CUTOFF_MS)
                width = WIDTH_MS[timeframe]
                frame = frame[(frame.t_open_ms >= START_MS)
                              & (frame.t_open_ms + width <= CUTOFF_MS)].reset_index(drop=True)
                for setup in SETUPS:
                    for signal in generate_signals(frame, setup):
                        close_ms = int(frame.t_open_ms.iloc[signal.index]) + width
                        if close_ms not in minute_open:
                            continue
                        signals_by_entry[close_ms].append({
                            "symbol": symbol, "timeframe": timeframe,
                            "signal_close_ms": close_ms, "setup": setup,
                            "side": signal.side, "stop": signal.stop,
                        })

            signal_history = []
            blocked_until = defaultdict(int)
            emitted_for_symbol = 0
            for entry_ms in sorted(signals_by_entry):
                signal_history.extend(signals_by_entry[entry_ms])
                latest_close = {}
                for item in signal_history:
                    timeframe = item["timeframe"]
                    latest_close[timeframe] = max(
                        latest_close.get(timeframe, 0), item["signal_close_ms"])
                signal_history = [item for item in signal_history
                                  if item["signal_close_ms"] == latest_close[item["timeframe"]]
                                  and entry_ms - item["signal_close_ms"] <= WIDTH_MS[item["timeframe"]]]
                candidate = build_consensus(
                    signal_history, symbol=symbol, entry_ms=entry_ms,
                    entry_price=minute_open[entry_ms], min_timeframes=2)
                if candidate is None:
                    continue
                active_votes = {tf: vote for tf, vote in candidate["votes"].items()
                                if entry_ms >= blocked_until[tf]}
                if len(active_votes) < 2 or len({v["side"] for v in active_votes.values()}) != 1:
                    continue
                confidence_votes = len(active_votes)
                for timeframe, vote in active_votes.items():
                    horizon_end = entry_ms + MAX_HORIZON_BARS * WIDTH_MS[timeframe]
                    if horizon_end > CUTOFF_MS:
                        continue
                    forecast = dict(vote)
                    forecast.update({"event_id": candidate["event_id"] + ":" + timeframe,
                                     "symbol": symbol, "side": candidate["side"]})
                    lo = raw_times.searchsorted(entry_ms, side="left")
                    hi = raw_times.searchsorted(horizon_end, side="left")
                    scored = score_forecast(
                        forecast, raw.iloc[lo:hi].reset_index(drop=True))
                    emitted_for_symbol += 1
                    blocked_until[timeframe] = horizon_end
                    for bars in (10, 20):
                        result = scored[f"{bars}_bars"]
                        key = (timeframe, candidate["side"], bars)
                        total = totals[key]
                        total["events"] += 1
                        outcome = result["outcome"]
                        if outcome in ("TARGET", "STOP", "TIMEOUT"):
                            total[outcome.lower()] += 1
                            total["sum_net_r"] += result["net_r"] or 0.0
                        else:
                            total["unscorable"] += 1
                        confidence_key = (timeframe, candidate["side"], bars, confidence_votes)
                        confidence = confidence_totals[confidence_key]
                        confidence["events"] += 1
                        confidence_symbols[confidence_key][symbol] += 1
                        if outcome in ("TARGET", "STOP", "TIMEOUT"):
                            confidence[outcome.lower()] += 1
                            confidence["sum_net_r"] += result["net_r"] or 0.0
                        else:
                            confidence["unscorable"] += 1
                        for leverage in (4, 5):
                            lev = scored["leverage"][f"{leverage}x"][f"{bars}_bars"]
                            lev_total = leverage_totals[(timeframe, candidate["side"], bars, leverage)]
                            lev_total["events"] += 1
                            lev_outcome = lev["outcome"]
                            if lev_outcome in ("TARGET", "STOP", "LIQUIDATION", "TIMEOUT"):
                                lev_total[lev_outcome.lower()] += 1
                                lev_total["sum_net_r"] += lev["net_r"] or 0.0
                            else:
                                lev_total["unscorable"] += 1
            print(f"symbols {symbol_index}/{len(symbols)}: {symbol}; "
                  f"signals={sum(map(len, signals_by_entry.values()))}; "
                  f"forecasts={emitted_for_symbol}", flush=True)
    finally:
        db.close()

    outcome_rows = []
    for (timeframe, side, bars), values in sorted(
            totals.items(), key=lambda row: (WIDTH_MS[row[0][0]], row[0][1], row[0][2])):
        scored_n = values["target"] + values["stop"] + values["timeout"]
        outcome_rows.append({"timeframe": timeframe, "side": side, "horizon_bars": bars,
                             **values,
                             "target_first_precision": values["target"] / scored_n if scored_n else None,
                             "mean_net_r": values["sum_net_r"] / scored_n if scored_n else None})
    leverage_rows = []
    for (timeframe, side, bars, leverage), values in sorted(
            leverage_totals.items(),
            key=lambda row: (WIDTH_MS[row[0][0]], row[0][1], row[0][2], row[0][3])):
        scored_n = values["target"] + values["stop"] + values["liquidation"] + values["timeout"]
        leverage_rows.append({"timeframe": timeframe, "side": side,
                              "horizon_bars": bars, "leverage": leverage, **values,
                              "target_first_precision": values["target"] / scored_n if scored_n else None,
                              "mean_net_r": values["sum_net_r"] / scored_n if scored_n else None})
    report = {
        "stage": "EXPLORATORY_DEV_ONLY",
        "start_ms": START_MS,
        "cutoff_exclusive_ms": CUTOFF_MS,
        "start_utc": "2026-07-17T00:00:00Z",
        "cutoff_utc": "2026-10-09T00:00:00Z",
        "symbol_limit": symbol_limit,
        "symbols": symbols,
        "setups": SETUPS,
        "timeframes": TIMEFRAMES,
        "target_r_multiple": 2.0,
        "fee_round_trip": 0.001,
        "horizons_bars": [10, 20],
        "forecast_rows": sum(row["events"] for row in outcome_rows if row["horizon_bars"] == 20),
        "outcomes": outcome_rows,
        "leveraged_outcomes": leverage_rows,
        "confidence_definition": "number of distinct active same-direction timeframe votes; raw score, not calibrated probability",
        "confidence_slices": summarize_confidence_slices(confidence_totals, confidence_symbols),
        "input": {"database": str(db_path), "database_size_bytes": db_path.stat().st_size,
                  "database_sha256": sha256_file(db_path),
                  "universe": str(universe_path),
                  "universe_sha256": sha256_file(universe_path)},
        "limitations": [
            "This development interval was previously explored and is not sealed or out-of-sample.",
            "Universe is the current collection list, not point-in-time membership; survivorship and listing bias remain.",
            "Confidence-slice coverage is conditional on the q≥2 consensus cohort, not all eligible decision times; registered baselines, event/symbol/day clustered confidence bounds, and slippage/depth are not computed.",
            "Per-timeframe outcomes share consensus events and symbols and are not independent samples.",
            "Approximate 4x/5x liquidation uses a fixed maintenance buffer, not Binance account-specific liquidation mechanics.",
            "Vote-count slices are post-hoc development exploration, not calibrated probabilities or a preregistered threshold.",
        ],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(f"report={output_path}")
    print(json.dumps(outcome_rows, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", help="read-only candles.sqlite")
    parser.add_argument("--universe", help="fixed symbol JSON list")
    parser.add_argument("--output", help="JSON report output path")
    parser.add_argument("--symbol-limit", type=int, default=50)
    parser.add_argument("--render-existing", help="render an existing JSON report as Markdown")
    parser.add_argument("--markdown-output", help="Markdown output path for --render-existing")
    args = parser.parse_args()
    if args.render_existing:
        if not args.markdown_output:
            parser.error("--markdown-output is required with --render-existing")
        report = json.loads(Path(args.render_existing).read_text())
        output = Path(args.markdown_output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(render_markdown(report))
        print(f"markdown_report={output.resolve()}")
        return
    if not args.db or not args.universe or not args.output:
        parser.error("--db, --universe, and --output are required for a new run")
    if args.symbol_limit <= 0:
        parser.error("--symbol-limit must be positive")
    run_experiment(args.db, args.universe, args.output, args.symbol_limit)


if __name__ == "__main__":
    main()
