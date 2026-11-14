"""Data store: Parquet files + SQLite provenance table. Single read interface: get_ohlcv().

Provenance per dataset: source, exchange, symbol, timeframe, fetched_at (UTC), row count,
first/last timestamp, sha256 of canonical CSV, library versions.
Binance access is PUBLIC market-data only (no API key is ever passed to ccxt here).
"""
import datetime as dt
import hashlib
import sqlite3
import time

import pandas as pd

from .config import DATA

OHLCV_DIR = DATA / "ohlcv"
META_DB = DATA / "meta.sqlite"
COLS = ["open", "high", "low", "close", "volume"]
TF_MS = {"5m": 300_000, "15m": 900_000, "1h": 3600_000, "4h": 14_400_000, "1d": 86_400_000}
PERIODS_PER_YEAR = {"5m": 288 * 365, "15m": 96 * 365, "1h": 24 * 365, "4h": 6 * 365, "1d": 365}

_SCHEMA = """CREATE TABLE IF NOT EXISTS datasets(
 id TEXT PRIMARY KEY, source TEXT, exchange TEXT, symbol TEXT, timeframe TEXT,
 fetched_at TEXT, rows INTEGER, first_ts TEXT, last_ts TEXT, sha256 TEXT, path TEXT, versions TEXT, note TEXT)"""


def _db():
    META_DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(META_DB)
    con.execute(_SCHEMA)
    return con


def canonical_hash(df):
    csv = df[COLS].to_csv(index=True, float_format="%.10g", date_format="%Y-%m-%dT%H:%M:%SZ")
    return hashlib.sha256(csv.encode()).hexdigest()


def dataset_id(source, symbol, timeframe):
    return "%s_%s_%s" % (source, symbol.replace("/", ""), timeframe)


def fetch_binance(symbol, timeframe, since, max_pages=80, exchange="binance"):
    """Public OHLCV via ccxt. `since` is a UTC datetime. Drops the still-open last candle."""
    import ccxt
    ex = getattr(ccxt, exchange)({"enableRateLimit": True, "timeout": 20000})  # no apiKey: public endpoints only (binance spot / binanceusdm futures)
    since_ms = int(since.timestamp() * 1000)
    rows = []
    for _ in range(max_pages):
        batch = ex.fetch_ohlcv(symbol, timeframe, since=since_ms, limit=1000)
        if not batch:
            break
        rows.extend(batch)
        nxt = batch[-1][0] + TF_MS[timeframe]
        if nxt <= since_ms or len(batch) < 2:
            break
        since_ms = nxt
        time.sleep(0.2)
    df = pd.DataFrame(rows, columns=["ts"] + COLS)
    df = df.drop_duplicates("ts").sort_values("ts")
    df.index = pd.to_datetime(df.pop("ts"), unit="ms", utc=True)
    df.index.name = "ts"
    now = pd.Timestamp.now(tz="UTC")
    df = df[df.index + pd.Timedelta(milliseconds=TF_MS[timeframe]) <= now]  # closed candles only
    return df.astype(float), ex.id


def save(df, source, exchange, symbol, timeframe, note=""):
    import ccxt
    OHLCV_DIR.mkdir(parents=True, exist_ok=True)
    did = dataset_id(source, symbol, timeframe)
    path = OHLCV_DIR / (did + ".parquet")
    tmp = path.with_suffix(".tmp")
    df.to_parquet(tmp)
    tmp.replace(path)                    # atomic: readers never see a half-written parquet
    meta = (did, source, exchange, symbol, timeframe,
            dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), len(df),
            df.index[0].isoformat(), df.index[-1].isoformat(), canonical_hash(df),
            str(path.relative_to(DATA.parent)), "pandas=%s ccxt=%s" % (pd.__version__, ccxt.__version__), note)
    with _db() as con:
        con.execute("INSERT OR REPLACE INTO datasets VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", meta)
    return meta


def list_datasets():
    with _db() as con:
        cur = con.execute("SELECT * FROM datasets ORDER BY id")
        names = [d[0] for d in cur.description]
        return [dict(zip(names, r)) for r in cur.fetchall()]


def get_ohlcv(symbol, timeframe, source="binance", start=None, end=None, verify=True):
    """THE single read interface. Verifies the stored hash before returning data."""
    did = dataset_id(source, symbol, timeframe)
    with _db() as con:
        row = con.execute("SELECT sha256, path FROM datasets WHERE id=?", (did,)).fetchone()
    if row is None:
        raise KeyError("dataset not found: %s" % did)
    for _attempt in range(4):            # a writer may sit between the parquet swap and the metadata update
        df = pd.read_parquet(DATA.parent / row[1])
        if not verify or canonical_hash(df) == row[0]:
            break
        time.sleep(0.5)
        with _db() as con:
            row = con.execute("SELECT sha256, path FROM datasets WHERE id=?", (did,)).fetchone()
    if verify and canonical_hash(df) != row[0]:
        raise ValueError("hash mismatch for %s: stored data differs from recorded provenance" % did)
    if start is not None:
        df = df[df.index >= pd.Timestamp(start, tz="UTC")]
    if end is not None:
        df = df[df.index <= pd.Timestamp(end, tz="UTC")]
    return df


def meta_of(symbol, timeframe, source="binance"):
    did = dataset_id(source, symbol, timeframe)
    for m in list_datasets():
        if m["id"] == did:
            return m
    raise KeyError(did)


def verify_all():
    out = []
    for m in list_datasets():
        df = pd.read_parquet(DATA.parent / m["path"])
        out.append({"id": m["id"], "ok": canonical_hash(df) == m["sha256"], "rows": len(df)})
    return out


def update_incremental(source, ccxt_exchange, ccxt_symbol, symbol, timeframe):
    """Append the newest CLOSED candles to an existing dataset (public GET only) and re-record provenance. Returns rows added."""
    did = dataset_id(source, symbol, timeframe)
    old = pd.read_parquet(OHLCV_DIR / (did + ".parquet"))
    since = old.index[-1].to_pydatetime() - dt.timedelta(milliseconds=3 * TF_MS[timeframe])
    new, ex = fetch_binance(ccxt_symbol, timeframe, since, max_pages=6, exchange=ccxt_exchange)
    merged = pd.concat([old, new])
    merged = merged[~merged.index.duplicated(keep="last")].sort_index()
    if len(merged) == len(old):
        return 0
    save(merged, source, ex, symbol, timeframe, note="public OHLCV via ccxt, closed candles only (incrementally updated)")
    return len(merged) - len(old)
