"""UTC-aligned complete-bucket aggregation from stored 1m candles."""
import sqlite3
from datetime import datetime, timezone
import pandas as pd

TIMEFRAME_MINUTES = {"5m": 5, "30m": 30, "60m": 60}


def resample_frame(frame: pd.DataFrame, timeframe: str, now_ms=None) -> pd.DataFrame:
    """Aggregate only closed buckets containing every expected 1m row."""
    if timeframe not in TIMEFRAME_MINUTES:
        raise ValueError(f"unsupported timeframe: {timeframe}")
    width = TIMEFRAME_MINUTES[timeframe]
    now_ms = now_ms or int(datetime.now(timezone.utc).timestamp() * 1000)
    df = frame.copy()
    if df.empty:
        return df.assign(bucket=pd.Series(dtype="int64"))
    df["t_open_ms"] = df["t_open_ms"].astype("int64")
    df["bucket"] = (df["t_open_ms"] // (width * 60_000)) * (width * 60_000)
    df = df[(df["t_open_ms"] - df["bucket"]) % 60_000 == 0]
    grouped = df.groupby("bucket", sort=True)
    output = grouped.agg(o=("o", "first"), h=("h", "max"), l=("l", "min"),
                         c=("c", "last"), v=("v", "sum"), quote_v=("quote_v", "sum"),
                         trades=("trades", "sum"), count=("t_open_ms", "nunique"))
    output = output[output["count"] == width].drop(columns="count")
    output = output[output.index + width * 60_000 <= now_ms]
    output.index.name = "t_open_ms"
    return output.reset_index()


def load_resampled(db: sqlite3.Connection, symbol: str, timeframe: str) -> pd.DataFrame:
    """Load a symbol's minute rows from SQLite and resample them."""
    frame = pd.read_sql_query("SELECT t_open_ms,o,h,l,c,v,quote_v,trades FROM candles "
                              "WHERE symbol=? ORDER BY t_open_ms", db, params=(symbol,))
    return resample_frame(frame, timeframe)
