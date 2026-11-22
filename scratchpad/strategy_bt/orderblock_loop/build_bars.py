"""Build 15m/1h/4h bars from Binance UM 1m klines (cutoff 2026-05-31 23:59 UTC).

Output: $TRADING_DATA_DIR/cache/orderblock/bars/<tf>/<SYMBOL>.parquet + MANIFEST.csv
Columns: open_time(ms UTC), open, high, low, close, volume, quote_volume, count, n_min, complete.
`complete` = all expected 1m rows present in the bar. Missing minutes are never filled; bars
with no 1m rows are absent. Rows from 2026-06-01 00:00 UTC onward are never read into bars.
Run inside bb_stoch_stc/.venv:  nice -n 10 python build_bars.py [--symbols A B]
"""
import argparse
import csv
import hashlib
import os
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

BASE = Path(os.environ.get("TRADING_DATA_DIR", Path.home() / "CODE/trading_data"))
SRC = BASE / "external/crypto/binance/um_klines_1m"
OUT = BASE / "cache/orderblock/bars"
CUTOFF_MS = int(pd.Timestamp("2026-06-01", tz="UTC").timestamp() * 1000)
TFS = {"15m": 15, "1h": 60, "4h": 240}
COLS = ["open_time", "open", "high", "low", "close", "volume", "quote_volume", "count"]


def load_1m(sym_dir):
    parts = []
    for f in sorted(sym_dir.glob("*.parquet")):
        if f.stem >= "2026-06":
            continue
        t = pq.read_table(f, columns=COLS).to_pandas()
        parts.append(t[t.open_time < CUTOFF_MS])
    df = pd.concat(parts, ignore_index=True)
    return df.drop_duplicates("open_time").sort_values("open_time").reset_index(drop=True)


def resample(df, minutes):
    span = minutes * 60_000
    key = (df.open_time // span) * span
    g = df.groupby(key, sort=True)
    out = pd.DataFrame({
        "open": g["open"].first(), "high": g["high"].max(), "low": g["low"].min(),
        "close": g["close"].last(), "volume": g["volume"].sum(),
        "quote_volume": g["quote_volume"].sum(), "count": g["count"].sum(),
        "n_min": g["open_time"].size(),
    })
    out.index.name = "open_time"
    out = out.reset_index()
    out["complete"] = out["n_min"] == minutes
    return out


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", nargs="*")
    args = ap.parse_args()
    syms = args.symbols or sorted(p.name for p in SRC.iterdir() if p.is_dir())
    rows = []
    for s in syms:
        df = load_1m(SRC / s)
        for tf, m in TFS.items():
            b = resample(df, m)
            dest = OUT / tf / f"{s}.parquet"
            dest.parent.mkdir(parents=True, exist_ok=True)
            pq.write_table(pa.Table.from_pandas(b, preserve_index=False), dest, compression="zstd")
            rows.append(dict(symbol=s, tf=tf, rows=len(b), incomplete=int((~b.complete).sum()),
                             first=int(b.open_time.iloc[0]), last=int(b.open_time.iloc[-1]),
                             src_1m_rows=len(df), sha256=sha256(dest)))
        print(s, len(df), flush=True)
        del df
    mf = OUT / "MANIFEST.csv"
    with open(mf, "a" if mf.exists() and args.symbols else "w", newline="") as fh:
        w = csv.DictWriter(fh, list(rows[0]))
        if not (mf.exists() and args.symbols and mf.stat().st_size):
            w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    main()
