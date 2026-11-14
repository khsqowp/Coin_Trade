"""US equity / ETF DAILY history bootstrap (research use). Read-only public market data, cached to disk.

What it does:
  * Fetches full daily OHLCV history for a small, explicit list of US tickers from the unofficial, key-less Yahoo Finance
    chart endpoint (GET https://query1.finance.yahoo.com/v8/finance/chart/<SYM>?period1=..&period2=..&interval=1d&events=div,split).
  * Stores the RAW vendor fields (split-adjusted open/high/low/close, dividend+split-adjusted 'adjclose', volume) and the
    dividend / split events, so adjustments can be audited, plus a provenance sidecar (url, fetched_at UTC, sha256 of the
    response body, row count, first/last date).
  * Cache: data/us_daily/<SYM>.parquet (+ <SYM>.meta.json, <SYM>.events.json). A cached file younger than max_age_h is
    returned without any network call. One request per symbol; >= MIN_INTERVAL_S between requests; bounded retries with
    backoff on HTTP 429/5xx; never hammers the endpoint.
  * Negative cache data/us_daily/missing/<SYM>.json for symbols the vendor does not serve (typically delisted names), so a
    universe re-run does not re-hit the endpoint for them for 30 days.
  * Drops the current day's bar until 16:30 America/New_York (same completeness rule as tp.news._et_close_passed).
  * validate(): data-quality checks (NaN, non-positive prices, OHLC inconsistency, duplicate dates, extreme daily moves,
    missing sessions versus a reference calendar, implied dividend-adjustment factor jumps).

What it does NOT do:
  * No orders, no accounts, no broker, no API keys or secrets of any kind. The only allowed host/path prefix is the
    public chart endpoint (allow-list enforced in _get). There is no order code in this module, ever.
  * It is not a point-in-time / survivorship-free database: Yahoo serves today's view of history (current split/dividend
    adjustments, only tickers that still exist). Delisted names are unavailable. Treat it as a research convenience.
  * It is NOT wired into tp.news (which keeps its own 5-year rolling Yahoo pull into data/ohlcv) or into any forward
    tracker / export. Separate directory, separate cache.
"""
import datetime as dt
import hashlib
import json
import time
from zoneinfo import ZoneInfo

import pandas as pd
import requests

from .config import DATA

US_DIR = DATA / "us_daily"
HOST = "https://query1.finance.yahoo.com"
ALLOWED_PREFIX = "/v8/finance/chart/"
MIN_INTERVAL_S = 2.0
MAX_TRIES = 4
UA = {"User-Agent": "Mozilla/5.0 (research; daily bars; low rate)"}
_LAST = {"t": 0.0}


class FetchError(RuntimeError):
    pass


def _get(path, params):
    if not path.startswith(ALLOWED_PREFIX):
        raise FetchError("path not allowed: " + path)
    last_err = None
    for i in range(MAX_TRIES):
        wait = MIN_INTERVAL_S - (time.time() - _LAST["t"])
        if wait > 0:
            time.sleep(wait)
        _LAST["t"] = time.time()
        try:
            r = requests.get(HOST + path, params=params, headers=UA, timeout=30)
        except requests.RequestException as e:     # network error -> retry with backoff
            last_err = "%s: %s" % (type(e).__name__, e)
            time.sleep(5 * (i + 1))
            continue
        if r.status_code == 200:
            return r.url, r.content
        last_err = "HTTP %s" % r.status_code
        if r.status_code in (429, 500, 502, 503, 504):
            time.sleep(min(int(r.headers.get("Retry-After", "0") or 0), 300) or 10 * (i + 1))
            continue
        break                                       # 4xx other than 429: do not retry
    raise FetchError("yahoo %s failed: %s" % (path, last_err))


def et_close_passed(bar_date, now):
    close = dt.datetime.combine(bar_date, dt.time(16, 30), tzinfo=ZoneInfo("America/New_York"))
    return now >= close.astimezone(dt.timezone.utc)


def parse_chart(body, now=None):
    """Vendor JSON -> (DataFrame[open,high,low,close,adjclose,volume] indexed by NY session date, events dict)."""
    now = now or dt.datetime.now(dt.timezone.utc)
    j = json.loads(body)
    res = (j.get("chart") or {}).get("result")
    if not res:
        raise FetchError("no result: %s" % str((j.get("chart") or {}).get("error"))[:200])
    r = res[0]
    q = r["indicators"]["quote"][0]
    adj = (r["indicators"].get("adjclose") or [{}])[0].get("adjclose")
    if adj is None:
        adj = q["close"]
    # Timestamps are the session open in exchange time; convert to the NY calendar date (not UTC date) to avoid off-by-one.
    ts = pd.to_datetime(r["timestamp"], unit="s", utc=True).tz_convert("America/New_York")
    idx = pd.DatetimeIndex(ts.date, name="date")
    df = pd.DataFrame({"open": q["open"], "high": q["high"], "low": q["low"], "close": q["close"],
                       "adjclose": adj, "volume": q["volume"]}, index=idx).astype(float)
    df = df[~df.index.duplicated(keep="last")].sort_index()
    df = df[[et_close_passed(d.date(), now) for d in df.index]]
    ev = r.get("events") or {}
    events = {"dividends": sorted([(pd.Timestamp(int(v["date"]), unit="s").strftime("%Y-%m-%d"), v["amount"])
                                   for v in (ev.get("dividends") or {}).values()]),
              "splits": sorted([(pd.Timestamp(int(v["date"]), unit="s").strftime("%Y-%m-%d"), v.get("splitRatio"))
                                for v in (ev.get("splits") or {}).values()])}
    return df, events


def _paths(sym):
    s = sym.replace("^", "IDX_")
    return US_DIR / (s + ".parquet"), US_DIR / (s + ".meta.json"), US_DIR / (s + ".events.json")


def _missing_path(sym):
    return US_DIR / "missing" / (sym.replace("^", "IDX_") + ".json")


def vendor_meta(body):
    """Identity fields from the vendor response (used to audit ticker reuse: same ticker, different company)."""
    m = ((json.loads(body).get("chart") or {}).get("result") or [{}])[0].get("meta") or {}
    return {k: m.get(k) for k in ("longName", "shortName", "instrumentType", "exchangeName", "currency", "firstTradeDate")}


def fetch(sym, start="1990-01-01", max_age_h=20.0, refresh=False):
    """Cached full-history daily bars for one symbol. Returns the raw-field DataFrame (see parse_chart)."""
    p, pm, pe = _paths(sym)
    pmiss = _missing_path(sym)
    if pmiss.exists() and not refresh:          # negative cache: symbol had no data (e.g. delisted); retry after 30 days
        miss = json.loads(pmiss.read_text())
        if (dt.datetime.now(dt.timezone.utc) - dt.datetime.fromisoformat(miss["at"])).days < 30:
            raise FetchError("%s: cached not-found (%s)" % (sym, miss["error"][:80]))
    if p.exists() and pm.exists() and not refresh:
        meta = json.loads(pm.read_text())
        age = (dt.datetime.now(dt.timezone.utc) - dt.datetime.fromisoformat(meta["fetched_at"])).total_seconds() / 3600
        if age < max_age_h:
            return pd.read_parquet(p)
    p1 = int(pd.Timestamp(start, tz="UTC").timestamp())
    p2 = int(time.time()) + 86400
    try:
        url, body = _get(ALLOWED_PREFIX + sym, {"period1": p1, "period2": p2, "interval": "1d", "events": "div,split",
                                                "includeAdjustedClose": "true"})
        df, events = parse_chart(body)
        if len(df) < 50:
            raise FetchError("%s: only %d rows" % (sym, len(df)))
    except FetchError as e:
        if "HTTP 404" in str(e) or "no result" in str(e) or "only" in str(e):
            pmiss.parent.mkdir(parents=True, exist_ok=True)
            pmiss.write_text(json.dumps({"symbol": sym, "error": str(e)[:300], "at": dt.datetime.now(dt.timezone.utc).isoformat()}))
        raise
    US_DIR.mkdir(parents=True, exist_ok=True)
    df.to_parquet(p)
    pe.write_text(json.dumps(events))
    pm.write_text(json.dumps({"symbol": sym, "source": "yahoo chart v8 (unofficial, key-less)", "url": url,
                              "fetched_at": dt.datetime.now(dt.timezone.utc).isoformat(), "sha256": hashlib.sha256(body).hexdigest(),
                              "rows": len(df), "first": str(df.index[0].date()), "last": str(df.index[-1].date()),
                              "vendor": vendor_meta(body)}, indent=1))
    return df


def fetch_many(symbols, **kw):
    """Fetch a list; one failure does not stop the rest. Returns ({sym: df}, {sym: error})."""
    out, err = {}, {}
    for s in symbols:
        try:
            out[s] = fetch(s, **kw)
        except Exception as e:      # noqa: BLE001  report, continue
            err[s] = "%s: %s" % (type(e).__name__, str(e)[:200])
    return out, err


def load(sym):
    """Cache only, no network."""
    return pd.read_parquet(_paths(sym)[0])


def adjusted(df):
    """Total-return-adjusted OHLC: scale split-adjusted OHLC by adjclose/close (dividends reinvested at the ex-date close)."""
    f = df["adjclose"] / df["close"]
    out = df[["open", "high", "low", "close"]].mul(f, axis=0)
    out["volume"] = df["volume"]
    return out


def validate(df, ref_dates=None, jump=0.15):
    """Data-quality report (dict). ref_dates: reference session calendar (e.g. SPY dates) for missing-session checks."""
    d = df.dropna(subset=["close"])
    rep = {"rows": int(len(df)), "first": str(df.index[0].date()), "last": str(df.index[-1].date()),
           "nan_rows": int(df[["open", "high", "low", "close"]].isna().any(axis=1).sum()),
           "nonpositive": int((d[["open", "high", "low", "close"]] <= 0).any(axis=1).sum()),
           "dup_dates": int(df.index.duplicated().sum()),
           "ohlc_inconsistent": int(((d["low"] > d[["open", "close"]].min(axis=1) * 1.0001) |
                                     (d["high"] < d[["open", "close"]].max(axis=1) * 0.9999)).sum()),
           "zero_volume_days": int((d["volume"] <= 0).sum())}
    r = d["adjclose"].pct_change().dropna()
    big = r[r.abs() > jump]
    rep["extreme_moves"] = [(str(i.date()), round(float(v), 4)) for i, v in big.items()]
    f = (d["adjclose"] / d["close"])
    fj = f.pct_change().dropna()
    rep["adj_factor_jumps_gt_5pct"] = [(str(i.date()), round(float(v), 4)) for i, v in fj[fj.abs() > 0.05].items()]
    if ref_dates is not None:
        ref = pd.DatetimeIndex(ref_dates)
        ref = ref[(ref >= d.index[0]) & (ref <= d.index[-1])]
        rep["missing_vs_ref"] = int(len(ref.difference(d.index)))
        rep["extra_vs_ref"] = int(len(d.index.difference(ref)))
    return rep
