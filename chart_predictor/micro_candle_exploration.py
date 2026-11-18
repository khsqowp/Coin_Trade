"""Read-only, fixed-rule micro-candle diagnostics for six liquid USDT-M symbols.

This script does not trade, mutate the source database, or produce an M2 result.
It reproduces one-bar close-location M1 diagnostics, three-bar event counts, and
the outcome-blind phase-2 expansion/compression feasibility gate.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import sqlite3
from pathlib import Path

SYMBOLS = ("BNBUSDT", "BTCUSDT", "DOGEUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT")
SEED = 20261118
BLOCK_DAYS = 7
BOOTSTRAP_REPLICATES = 2_000


def _connect_readonly(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True)


def _daily_close_location(db: sqlite3.Connection) -> dict:
    db.create_function(
        "fixed_random_side", 2,
        lambda symbol, open_ms: 1 if hashlib.sha256(
            f"{SEED}|{symbol}|{open_ms}".encode()
        ).digest()[0] & 1 else -1,
        deterministic=True,
    )
    symbols = ",".join("?" for _ in SYMBOLS)
    sql = f"""WITH w AS (
      SELECT symbol,open_ms,date(open_ms/1000,'unixepoch') AS day,
             open,high,low,close,
             lead(open_ms) OVER z AS next_ms,
             lead(close) OVER z AS next_close
      FROM candles WHERE symbol IN ({symbols})
      WINDOW z AS (PARTITION BY symbol ORDER BY open_ms)
    ), x AS (
      SELECT symbol,day,
        CASE WHEN close>=low+0.8*(high-low) THEN 1
             WHEN close<=low+0.2*(high-low) THEN -1 ELSE 0 END AS signal,
        CASE WHEN close>open THEN 1 WHEN close<open THEN -1 ELSE 0 END AS momentum,
        fixed_random_side(symbol,open_ms) AS random_side,
        CASE WHEN next_close>close THEN 1
             WHEN next_close<close THEN -1 ELSE 0 END AS actual
      FROM w
      WHERE next_ms=open_ms+60000
        AND open_ms%60000=0
        AND high>low
        AND high>=low AND high>=open AND high>=close
        AND low<=open AND low<=close AND low>0
    )
    SELECT day,count(*) AS eligible,
      sum(signal!=0) AS issued,
      sum(signal!=0 AND actual!=0) AS directional,
      sum((signal=1 AND actual=1) OR (signal=-1 AND actual=-1)) AS hits,
      sum(signal!=0 AND ((momentum=1 AND actual=1) OR (momentum=-1 AND actual=-1))) AS momentum_hits,
      sum(signal!=0 AND ((random_side=1 AND actual=1) OR (random_side=-1 AND actual=-1))) AS random_hits
    FROM x GROUP BY day ORDER BY day"""
    rows = list(db.execute(sql, SYMBOLS))
    rng = random.Random(SEED)
    total_days = len(rows)
    block_count = (total_days + BLOCK_DAYS - 1) // BLOCK_DAYS
    samples = []
    for _ in range(BOOTSTRAP_REPLICATES):
        eligible = issued = directional = hits = momentum_hits = random_hits = 0
        starts = [rng.randrange(total_days) for _ in range(block_count)]
        for offset in range(total_days):
            start = starts[offset // BLOCK_DAYS]
            k = offset % BLOCK_DAYS
            (_, day_eligible, day_issued, day_directional, day_hits,
             day_momentum_hits, day_random_hits) = rows[(start + k) % total_days]
            eligible += day_eligible
            issued += day_issued
            directional += day_directional
            hits += day_hits
            momentum_hits += day_momentum_hits
            random_hits += day_random_hits
        samples.append((hits / issued, hits / directional,
                        (hits - momentum_hits) / issued,
                        (hits - random_hits) / issued))
    sorted_samples = [sorted(sample[index] for sample in samples) for index in range(4)]
    n_eligible = sum(row[1] for row in rows)
    n_issued = sum(row[2] for row in rows)
    n_directional = sum(row[3] for row in rows)
    n_hits = sum(row[4] for row in rows)
    n_momentum_hits = sum(row[5] for row in rows)
    n_random_hits = sum(row[6] for row in rows)
    return {
        "utc_dates": total_days,
        "first_utc_date": rows[0][0],
        "last_utc_date": rows[-1][0],
        "eligible_anchors": n_eligible,
        "issued": n_issued,
        "coverage": n_issued / n_eligible,
        "directional_nonflat": n_directional,
        "hits": n_hits,
        "all_issued_accuracy": n_hits / n_issued,
        "nonflat_direction_accuracy": n_hits / n_directional,
        "matched_momentum_accuracy": n_momentum_hits / n_issued,
        "fixed_sha256_random_accuracy": n_random_hits / n_issued,
        "paired_accuracy_difference_vs_momentum": (n_hits - n_momentum_hits) / n_issued,
        "paired_accuracy_difference_vs_random": (n_hits - n_random_hits) / n_issued,
        "shared_date_circular_block_bootstrap": {
            "block_days": BLOCK_DAYS,
            "replicates": BOOTSTRAP_REPLICATES,
            "seed": SEED,
            "all_issued_95pct": [sorted_samples[0][49], sorted_samples[0][1949]],
            "nonflat_direction_95pct": [sorted_samples[1][49], sorted_samples[1][1949]],
            "paired_difference_vs_momentum_95pct": [sorted_samples[2][49], sorted_samples[2][1949]],
            "paired_difference_vs_random_95pct": [sorted_samples[3][49], sorted_samples[3][1949]],
        },
    }


def _three_bar_counts(db: sqlite3.Connection) -> dict:
    symbols = ",".join("?" for _ in SYMBOLS)
    sql = f"""WITH w AS (
      SELECT symbol,open_ms,open,high,low,close,
        lag(open_ms,1) OVER z AS ms1, lag(open_ms,2) OVER z AS ms2,
        lag(open,1) OVER z AS o1, lag(high,1) OVER z AS h1,
        lag(low,1) OVER z AS l1, lag(close,1) OVER z AS c1,
        lag(open,2) OVER z AS o2, lag(high,2) OVER z AS h2,
        lag(low,2) OVER z AS l2, lag(close,2) OVER z AS c2
      FROM candles WHERE symbol IN ({symbols})
      WINDOW z AS (PARTITION BY symbol ORDER BY open_ms)
    ), x AS (
      SELECT symbol,
        CASE WHEN open_ms%60000=0 AND open_ms-ms1=60000 AND ms1-ms2=60000 THEN 1 ELSE 0 END AS eligible,
        CASE WHEN open_ms%60000=0 AND open_ms-ms1=60000 AND ms1-ms2=60000 AND c2>o2
          AND c1<o1 AND h1-l1<=0.5*(h2-l2) AND close>h1 THEN 1 ELSE 0 END AS long_signal,
        CASE WHEN open_ms%60000=0 AND open_ms-ms1=60000 AND ms1-ms2=60000 AND c2<o2
          AND c1>o1 AND h1-l1<=0.5*(h2-l2) AND close<l1 THEN 1 ELSE 0 END AS short_signal
      FROM w
    )
    SELECT symbol,sum(eligible),sum(long_signal),sum(short_signal)
    FROM x GROUP BY symbol ORDER BY symbol"""
    result = {}
    for symbol, eligible, longs, shorts in db.execute(sql, SYMBOLS):
        result[symbol] = {"eligible_anchors": eligible, "long": longs, "short": shorts}
    return result


def _phase2_feasibility(db: sqlite3.Connection) -> dict:
    symbols = ",".join("?" for _ in SYMBOLS)
    sql = f"""WITH a AS (
      SELECT symbol,open_ms,open,high,low,close,high-low AS candle_range,
        median(high-low) OVER (PARTITION BY symbol ORDER BY open_ms
          ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING) AS prior_median,
        lag(open_ms,20) OVER (PARTITION BY symbol ORDER BY open_ms) AS ms20,
        lag(open,1) OVER (PARTITION BY symbol ORDER BY open_ms) AS prior_open,
        lag(close,1) OVER (PARTITION BY symbol ORDER BY open_ms) AS prior_close,
        lag(high-low,1) OVER (PARTITION BY symbol ORDER BY open_ms) AS prior_range,
        sum(CASE WHEN high>=low AND high>=open AND high>=close
                  AND low<=open AND low<=close AND low>0 AND open_ms%60000=0 THEN 1 ELSE 0 END)
          OVER (PARTITION BY symbol ORDER BY open_ms
                ROWS BETWEEN 20 PRECEDING AND CURRENT ROW) AS valid_21
      FROM candles WHERE symbol IN ({symbols})
    ), x AS (
      SELECT symbol,
        CASE WHEN ms20 IS NOT NULL AND open_ms%60000=0 AND open_ms-ms20=1200000 AND valid_21=21
             THEN 1 ELSE 0 END AS eligible,
        CASE WHEN ms20 IS NOT NULL AND open_ms%60000=0 AND open_ms-ms20=1200000 AND valid_21=21
          AND prior_median>0 AND prior_range>=prior_median
          AND candle_range<=0.5*prior_median AND prior_close>prior_open
          THEN 1 ELSE 0 END AS long_signal,
        CASE WHEN ms20 IS NOT NULL AND open_ms%60000=0 AND open_ms-ms20=1200000 AND valid_21=21
          AND prior_median>0 AND prior_range>=prior_median
          AND candle_range<=0.5*prior_median AND prior_close<prior_open
          THEN 1 ELSE 0 END AS short_signal
      FROM a
    )
    SELECT symbol,sum(eligible),sum(long_signal),sum(short_signal)
    FROM x GROUP BY symbol ORDER BY symbol"""
    result = {}
    for symbol, eligible, longs, shorts in db.execute(sql, SYMBOLS):
        result[symbol] = {"eligible_21bar_anchors": eligible, "long": longs, "short": shorts}
    total_eligible = sum(row["eligible_21bar_anchors"] for row in result.values())
    total_signals = sum(row["long"] + row["short"] for row in result.values())
    return {
        "symbols_with_signals": sum(row["long"] + row["short"] > 0 for row in result.values()),
        "eligible_anchors": total_eligible,
        "signals": total_signals,
        "coverage": total_signals / total_eligible if total_eligible else 0.0,
        "by_symbol": result,
    }


def run(db_path: Path) -> dict:
    db = _connect_readonly(db_path)
    try:
        metadata = db.execute(
            "SELECT min(open_ms),max(open_ms),count(*) FROM candles WHERE symbol IN (" +
            ",".join("?" for _ in SYMBOLS) + ")", SYMBOLS
        ).fetchone()
        invalid = db.execute(
            "SELECT count(*) FROM candles WHERE symbol IN (" +
            ",".join("?" for _ in SYMBOLS) +
            ") AND (high<low OR high<open OR high<close OR low>open OR low>close OR low<=0)",
            SYMBOLS,
        ).fetchone()[0]
        off_grid = db.execute(
            "SELECT count(*) FROM candles WHERE symbol IN (" +
            ",".join("?" for _ in SYMBOLS) + ") AND open_ms%60000!=0",
            SYMBOLS,
        ).fetchone()[0]
        return {
            "database": str(db_path.resolve()),
            "symbols": list(SYMBOLS),
            "rows_min_open_ms_max_open_ms": list(metadata),
            "invalid_ohlc_rows": invalid,
            "off_grid_rows": off_grid,
            "one_bar_close_location_m1": _daily_close_location(db),
            "three_bar_impulse_pullback_confirmation_outcome_blind_counts": _three_bar_counts(db),
            "phase2_expansion_compression_feasibility_only": _phase2_feasibility(db),
            "m2_outcomes_read": False,
        }
    finally:
        db.close()


def main() -> None:
    default_db = Path(__file__).parent / "data" / "vision_pit_dev_sample.sqlite"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=default_db)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = run(args.db)
    encoded = json.dumps(result, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded + "\n", encoding="utf-8")
    print(encoded)


if __name__ == "__main__":
    main()
