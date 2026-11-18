"""Outcome-blind frequency screen for the frozen two-bar micro pattern."""
from __future__ import annotations

import argparse
import json
import math
import sqlite3
from collections import deque
from pathlib import Path
from statistics import median

MINUTE_MS = 60_000
WINDOW = 20
COOLDOWN_BARS = 10


def screen(database: Path) -> dict:
    uri = f"file:{database.resolve()}?mode=ro"
    db = sqlite3.connect(uri, uri=True)
    try:
        symbols = [r[0] for r in db.execute("SELECT DISTINCT symbol FROM candles ORDER BY symbol")]
        per_symbol = []
        for symbol in symbols:
            rows = db.execute(
                "SELECT t_open_ms,o,h,l,c FROM candles WHERE symbol=? ORDER BY t_open_ms",
                (symbol,),
            )
            history = deque(maxlen=WINDOW)
            previous = None
            prev_close_before_previous = None
            last_ts = None
            scheduled = eligible = raw = longs = shorts = cooled = 0
            last_signal_index = -COOLDOWN_BARS
            row_count = 0
            for row in rows:
                ts, op, high, lo, close = (int(row[0]), *(float(x) for x in row[1:]))
                if last_ts is not None and ts - last_ts != MINUTE_MS:
                    raise ValueError(f"non-contiguous timestamps for {symbol}; no outcomes queried")
                vals = (op, high, lo, close)
                if not all(math.isfinite(x) for x in vals):
                    raise ValueError(f"non-finite OHLC for {symbol}; no outcomes queried")

                if previous is not None:
                    a_ts, a_op, a_high, a_low, a_close = previous
                    a_range = a_high - a_low
                    if len(history) == WINDOW:
                        scheduled += 1
                    if (len(history) == WINDOW and a_range > 0 and high > lo
                            and a_close != a_op and close != op):
                        eligible += 1
                        impulse = (
                            a_range >= median(history)
                            and abs(a_close - a_op) / a_range >= 0.60
                        )
                        inside = high <= a_high and lo >= a_low
                        close_position = (close - a_low) / a_range
                        long_signal = (
                            impulse and inside and a_close < a_op
                            and close_position >= 0.75
                        )
                        short_signal = (
                            impulse and inside and a_close > a_op
                            and close_position <= 0.25
                        )
                        if long_signal or short_signal:
                            raw += 1
                            longs += int(long_signal)
                            shorts += int(short_signal)
                            if row_count - last_signal_index >= COOLDOWN_BARS:
                                cooled += 1
                                last_signal_index = row_count

                    # Add A's TR only after evaluating B so the rolling median
                    # excludes A and B. The first candle has no known prior close.
                    if prev_close_before_previous is not None:
                        tr = max(
                            a_high - a_low,
                            abs(a_high - prev_close_before_previous),
                            abs(a_low - prev_close_before_previous),
                        )
                        history.append(tr)
                    prev_close_before_previous = a_close

                previous = (ts, op, high, lo, close)
                last_ts = ts
                row_count += 1

            per_symbol.append({
                "symbol": symbol,
                "rows": row_count,
                "scheduled_anchors": scheduled,
                "eligible_anchors": eligible,
                "long_events": longs,
                "short_events": shorts,
                "raw_events": raw,
                "raw_coverage": raw / scheduled if scheduled else 0.0,
                "cooldown_events": cooled,
            })
        scheduled = sum(x["scheduled_anchors"] for x in per_symbol)
        eligible = sum(x["eligible_anchors"] for x in per_symbol)
        raw = sum(x["raw_events"] for x in per_symbol)
        cooldown = sum(x["cooldown_events"] for x in per_symbol)
        active_symbols = sum(x["cooldown_events"] > 0 for x in per_symbol)
        return {
            "database": str(database.resolve()),
            "symbols": len(symbols),
            "scheduled_anchors": scheduled,
            "eligible_anchors": eligible,
            "raw_events": raw,
            "raw_coverage": raw / scheduled if scheduled else 0.0,
            "cooldown_events": cooldown,
            "cooldown_active_symbols": active_symbols,
            "outcome_rows_read": 0,
            "target_stop_labels_read": 0,
            "gate_raw_coverage_ge_10pct": raw / scheduled >= 0.10 if scheduled else False,
            "gate_nonoverlap_n_ge_200_and_symbols_ge_20": cooldown >= 200 and active_symbols >= 20,
            "per_symbol": per_symbol,
        }
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("database", type=Path)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    result = screen(args.database)
    serialized = json.dumps(result, indent=2, sort_keys=True)
    if args.json:
        args.json.write_text(serialized + "\n")
    print(serialized)


if __name__ == "__main__":
    main()
