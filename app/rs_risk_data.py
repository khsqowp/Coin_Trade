"""Public Binance USDT-perp 1h klines + funding rate fetcher with local CSV cache.
Research only (rs_risk_*). Uses REST directly (no keys). Cache: trading/.rs_cache/
Run: python3.12 -m app.rs_risk_data
"""
from __future__ import annotations
import json, os, re, sys, time, urllib.error, urllib.request
from concurrent.futures import ThreadPoolExecutor
import pandas as pd

CACHE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".rs_cache")
BASE = "https://fapi.binance.com"
START_MS = int(pd.Timestamp("2021-12-01T00:00:00Z").timestamp() * 1000)
UNIVERSE = [
    "BTC", "ETH", "BNB", "XRP", "SOL", "TRX", "DOGE", "ZEC", "LINK", "XMR",
    "ADA", "XLM", "BCH", "LTC", "HBAR", "AVAX", "SUI", "UNI", "NEAR",
    "TAO", "AAVE", "ONDO", "THETA", "DOT", "ENA", "WLD", "ICP", "ETC",
    "POL", "QNT", "ALGO", "ATOM", "RENDER", "JUP", "ARB", "FIL", "VET",
    "CAKE", "TON", "MKR", "LDO", "CRV", "INJ", "OP", "APT", "IMX", "STX",
]


def _get(path: str, params: dict):
    q = "&".join(f"{k}={v}" for k, v in params.items())
    for attempt in range(20):
        try:
            with urllib.request.urlopen(f"{BASE}{path}?{q}", timeout=30) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "ignore")
            m = re.search(r"banned until (\d+)", body)
            wait = (int(m.group(1)) / 1000 - time.time() + 5) if m else 30 * (attempt + 1)
            print(f"  http {e.code} wait {wait:.0f}s", flush=True)
            time.sleep(min(max(wait, 5), 900))
        except Exception:  # noqa: BLE001
            time.sleep(2 + attempt)
    raise RuntimeError(f"fetch failed {path} {params}")


def fetch_klines(sym: str, interval: str = "1h") -> pd.DataFrame:
    rows, start = [], START_MS
    while True:
        b = _get("/fapi/v1/klines", {"symbol": sym, "interval": interval, "startTime": start, "limit": 1000})
        if not b:
            break
        rows.extend(b)
        time.sleep(0.5)
        start = b[-1][0] + 1
        if len(b) < 1000:
            break
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows).iloc[:, :6]
    df.columns = ["ts", "open", "high", "low", "close", "volume"]
    df["ts"] = pd.to_datetime(df["ts"], unit="ms", utc=True)
    df = df.set_index("ts").astype(float)
    return df[~df.index.duplicated()]


def fetch_funding(sym: str) -> pd.DataFrame:
    rows, start = [], START_MS
    while True:
        b = _get("/fapi/v1/fundingRate", {"symbol": sym, "startTime": start, "limit": 1000})
        if not b:
            break
        rows.extend(b)
        start = b[-1]["fundingTime"] + 1
        if len(b) < 1000:
            break
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df["ts"] = pd.to_datetime(df["fundingTime"], unit="ms", utc=True)
    df["rate"] = df["fundingRate"].astype(float)
    return df.set_index("ts")[["rate"]]


def _one(base: str):
    sym = f"{base}USDT"
    p1, p2 = f"{CACHE}/{base}_1h.csv.gz", f"{CACHE}/{base}_fund.csv.gz"
    if not os.path.exists(p1):
        k = fetch_klines(sym)
        if not k.empty:
            k.to_csv(p1)
    if not os.path.exists(p2):
        f = fetch_funding(sym)
        if not f.empty:
            f.to_csv(p2)
    return base, os.path.exists(p1)


def load_all() -> tuple[dict, dict]:
    k, f = {}, {}
    for b in UNIVERSE:
        p1, p2 = f"{CACHE}/{b}_1h.csv.gz", f"{CACHE}/{b}_fund.csv.gz"
        if os.path.exists(p1):
            k[b] = pd.read_csv(p1, index_col=0, parse_dates=True)
        if os.path.exists(p2):
            f[b] = pd.read_csv(p2, index_col=0, parse_dates=True)["rate"]
    return k, f


def main() -> None:
    os.makedirs(CACHE, exist_ok=True)
    for b in UNIVERSE:
        base, ok = _one(b)
        print(base, "ok" if ok else "MISSING", flush=True)


if __name__ == "__main__":
    main()
