"""News / feature collector. NO LLM, NO API KEYS. Runs in the `news` container (network, no env).

Storage: SQLite  data/news/news.sqlite  (+ periodic Parquet snapshots in data/news/parquet/).
Every row keeps: fetched_at (when WE saw it), source feed URL, item link, sha256 of the raw item text.
All external text is UNTRUSTED DATA: it is stored as plain text (tags stripped, length capped) and is never
interpreted, executed, or used to trigger any action by this module.

As-of rule: a consumer asking "what was known at T" must use  fetched_at <= T  AND  published_at <= T
(see `items_asof` / `features_asof`).  fetched_at is the authoritative knowledge time.
"""
import datetime as dt
import email.utils
import hashlib
import html
import json
import random
import re
import sqlite3
import time
import xml.etree.ElementTree as ET

import requests

from .config import DATA

NEWS_DIR = DATA / "news"
DB = NEWS_DIR / "news.sqlite"
STATUS = NEWS_DIR / "status.json"
UA = "tp-research-collector/1.0 (non-commercial personal research; low-rate polling)"
MAX_BODY = 3_000_000
TITLE_MAX, SUMMARY_MAX = 300, 600

# ---------------------------------------------------------------- source catalogue (max 5 sources)
# `urls` = primary first, then fallbacks (used only when the primary fails).
RSS_SOURCES = [
    dict(id="fed", market="global", every=600, urls=["https://www.federalreserve.gov/feeds/press_all.xml"]),
    dict(id="ecb", market="global", every=1800, urls=["https://www.ecb.europa.eu/rss/press.html"]),
    dict(id="coindesk", market="crypto", every=600,
         urls=["https://www.coindesk.com/arc/outboundfeeds/rss", "https://cointelegraph.com/rss"]),
    dict(id="yonhap_econ", market="kr", every=600,
         urls=["https://www.yna.co.kr/rss/economy.xml", "https://www.mk.co.kr/rss/30100041/"]),
    dict(id="bbc_business", market="global", every=600,
         urls=["https://feeds.bbci.co.uk/news/business/rss.xml",
               "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10001147"]),
]
GDELT_BASE = "https://api.gdeltproject.org/api/v2/doc/doc"
GDELT_QUERIES = {
    "monetary": '("federal reserve" OR "interest rate" OR "central bank" OR inflation) sourcelang:english',
    "geopolitics": '(sanctions OR tariff OR "trade war" OR ceasefire OR invasion OR embargo) sourcelang:english',
    "crypto_policy": '(bitcoin OR crypto OR stablecoin) (regulation OR SEC OR ban OR ETF) sourcelang:english',
    "korea": '(KOSPI OR "Bank of Korea" OR "South Korea economy") sourcelang:english',
}
GDELT_EVERY = 1800
HOST_MIN_INTERVAL = {"api.gdeltproject.org": 6.0}      # GDELT asks for <= 1 request / 5 s
DEFAULT_MIN_INTERVAL = 1.5

FEATURE_JOBS = [
    ("fng", 6 * 3600), ("binance_funding_oi", 300),
]
US_SYMBOLS = ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "BRK-B", "JPM", "V", "UNH", "XOM",
              "LLY", "AVGO", "WMT", "COST", "SPY", "QQQ"]

_SCHEMA = """
CREATE TABLE IF NOT EXISTS items(
 id TEXT PRIMARY KEY, source TEXT, market TEXT, feed_url TEXT, link TEXT, title TEXT, summary TEXT,
 published_at TEXT, fetched_at TEXT, raw_sha256 TEXT, lang TEXT, extra TEXT);
CREATE INDEX IF NOT EXISTS ix_items_fetched ON items(fetched_at);
CREATE TABLE IF NOT EXISTS item_revisions(
 id TEXT, seen_at TEXT, raw_sha256 TEXT, title TEXT, summary TEXT);
CREATE TABLE IF NOT EXISTS features(
 name TEXT, ts TEXT, value REAL, fetched_at TEXT, source_url TEXT, raw_sha256 TEXT, extra TEXT,
 PRIMARY KEY(name, ts));
CREATE TABLE IF NOT EXISTS fetch_log(
 at TEXT, job TEXT, url TEXT, ok INTEGER, http INTEGER, n_new INTEGER, note TEXT);
"""


def now_utc():
    return dt.datetime.now(dt.timezone.utc)


def iso(t):
    return t.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def db():
    NEWS_DIR.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB, timeout=30)
    con.execute("PRAGMA journal_mode=DELETE")   # readers may mount the dir read-only
    con.executescript(_SCHEMA)
    return con


# ---------------------------------------------------------------- text hygiene
_TAG = re.compile(r"<[^>]*>")
_CTRL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f​-‏‪-‮⁦-⁩]")
_WS = re.compile(r"\s+")


def clean_text(s, limit):
    s = html.unescape(str(s or ""))
    s = _TAG.sub(" ", s)
    s = html.unescape(s)
    s = _CTRL.sub(" ", s)
    return _WS.sub(" ", s).strip()[:limit]


def sha(*parts):
    h = hashlib.sha256()
    for p in parts:
        h.update(str(p).encode("utf-8", "replace"))
        h.update(b"\x1f")
    return h.hexdigest()


# ---------------------------------------------------------------- parsing
def _local(tag):
    return tag.rsplit("}", 1)[-1]


def parse_dt(s):
    if not s:
        return None
    s = s.strip()
    try:
        d = email.utils.parsedate_to_datetime(s)
    except (TypeError, ValueError):
        d = None
    if d is None:
        try:
            d = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
        except ValueError:
            return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=dt.timezone.utc)
    return d.astimezone(dt.timezone.utc)


def parse_feed(body):
    """RSS 2.0 / RSS 1.0 (rdf) / Atom -> list of dict(guid, link, title, summary, published, raw). Rejects DTD/entity tricks."""
    if len(body) > MAX_BODY:
        raise ValueError("feed too large")
    if b"<!entity" in body.lower():
        raise ValueError("entity declarations are not accepted")
    root = ET.fromstring(body)
    out = []
    for el in root.iter():
        if _local(el.tag) not in ("item", "entry"):
            continue
        f = {}
        for c in el:
            k = _local(c.tag)
            if k == "link" and not (c.text or "").strip() and c.get("href"):
                f.setdefault("link", c.get("href"))
            elif k in ("title", "link", "guid", "id", "description", "summary", "pubDate", "published", "updated", "date"):
                f.setdefault(k, (c.text or "").strip())
        pub = parse_dt(f.get("pubDate") or f.get("published") or f.get("updated") or f.get("date"))
        raw = "\n".join([f.get("title", ""), f.get("link", ""), f.get("description") or f.get("summary") or ""])
        out.append({"guid": f.get("guid") or f.get("id") or f.get("link") or f.get("title"),
                    "link": f.get("link", ""), "title": f.get("title", ""),
                    "summary": f.get("description") or f.get("summary") or "", "published": pub, "raw": raw})
    return out


# ---------------------------------------------------------------- HTTP with per-host pacing
_last_call = {}
_cache = {}      # url -> (etag, last_modified)


class FetchError(RuntimeError):
    def __init__(self, msg, http=None, retry_after=None):
        super().__init__(msg)
        self.http, self.retry_after = http, retry_after


def http_get(url, params=None, conditional=False, sleep=time.sleep):
    host = re.sub(r"^https?://([^/]+).*", r"\1", url)
    gap = HOST_MIN_INTERVAL.get(host, DEFAULT_MIN_INTERVAL)
    wait = _last_call.get(host, 0) + gap - time.monotonic()
    if wait > 0:
        sleep(wait)
    hdr = {"User-Agent": UA, "Accept": "application/xml,application/json,text/xml,*/*;q=0.5"}
    if conditional and url in _cache:
        etag, lm = _cache[url]
        if etag:
            hdr["If-None-Match"] = etag
        if lm:
            hdr["If-Modified-Since"] = lm
    try:
        r = requests.get(url, params=params, headers=hdr, timeout=20, stream=True, allow_redirects=True)
        body = r.raw.read(MAX_BODY + 1, decode_content=True)
    except requests.RequestException as e:
        _last_call[host] = time.monotonic()
        raise FetchError("network: %s" % type(e).__name__)
    _last_call[host] = time.monotonic()
    if r.status_code == 304:
        return 304, b""
    if r.status_code == 429 or r.status_code >= 500:
        ra = r.headers.get("Retry-After")
        raise FetchError("HTTP %s" % r.status_code, r.status_code, int(ra) if ra and ra.isdigit() else None)
    if r.status_code != 200:
        raise FetchError("HTTP %s" % r.status_code, r.status_code)
    if len(body) > MAX_BODY:
        raise FetchError("body too large")
    if conditional:
        _cache[url] = (r.headers.get("ETag"), r.headers.get("Last-Modified"))
    return 200, body


# ---------------------------------------------------------------- persistence
def store_items(con, source, market, feed_url, entries, fetched):
    """entries: list of dict(guid, link, title, summary, published, raw, extra?). Returns number of NEW items."""
    new = 0
    f_iso = iso(fetched)
    for e in entries:
        iid = sha(source, e["guid"])[:20]
        raw_h = sha(e["raw"])
        pub = e["published"]
        extra = {}
        if pub is None or pub > fetched + dt.timedelta(minutes=10):
            extra["published_clamped"] = True          # missing / future-dated => treat as first seen now
            pub = fetched
        extra.update(e.get("extra", {}))
        title, summ = clean_text(e["title"], TITLE_MAX), clean_text(e["summary"], SUMMARY_MAX)
        row = con.execute("SELECT raw_sha256 FROM items WHERE id=?", (iid,)).fetchone()
        if row is None:
            con.execute("INSERT INTO items VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                        (iid, source, market, feed_url, e["link"][:500], title, summ, iso(pub), f_iso, raw_h,
                         e.get("lang", ""), json.dumps(extra) if extra else None))
            new += 1
        elif row[0] != raw_h:                          # first-seen row stays immutable; edits are logged
            con.execute("INSERT INTO item_revisions VALUES (?,?,?,?,?)", (iid, f_iso, raw_h, title, summ))
    con.commit()
    return new


def store_feature(con, name, ts, value, fetched, url, raw, extra=None):
    cur = con.execute("INSERT OR IGNORE INTO features VALUES (?,?,?,?,?,?,?)",
                      (name, ts, float(value), iso(fetched), url, sha(raw), json.dumps(extra) if extra else None))
    return cur.rowcount


def log_fetch(con, job, url, ok, http, n_new, note=""):
    con.execute("INSERT INTO fetch_log VALUES (?,?,?,?,?,?,?)", (iso(now_utc()), job, url, int(ok), http, n_new, note[:200]))
    con.commit()


# ---------------------------------------------------------------- jobs
def job_rss(con, src, sleep=time.sleep):
    last = None
    for url in src["urls"]:
        try:
            code, body = http_get(url, conditional=True, sleep=sleep)
            if code == 304:
                log_fetch(con, src["id"], url, True, 304, 0)
                return 0
            entries = parse_feed(body)
            if not entries:
                raise FetchError("empty feed")
            n = store_items(con, src["id"], src["market"], url, entries, now_utc())
            log_fetch(con, src["id"], url, True, 200, n)
            return n
        except (FetchError, ET.ParseError, ValueError) as e:
            last = e
            log_fetch(con, src["id"], url, False, getattr(e, "http", None), 0, "%s: %s" % (type(e).__name__, e))
    raise last


def job_gdelt(con, qname, sleep=time.sleep):
    q = GDELT_QUERIES[qname]
    fetched = now_utc()
    new = 0
    code, body = http_get(GDELT_BASE, params={"query": q, "mode": "artlist", "maxrecords": 50, "format": "json",
                                              "timespan": "2h", "sort": "datedesc"}, sleep=sleep)
    if body.strip().startswith(b"{") or body.strip().startswith(b"["):
        j = json.loads(body or b"{}")
    else:
        raise FetchError("GDELT non-JSON response: %r" % clean_text(body[:80], 80))
    ents = []
    for a in j.get("articles", []):
        p = None
        try:
            p = dt.datetime.strptime(a.get("seendate", ""), "%Y%m%dT%H%M%SZ").replace(tzinfo=dt.timezone.utc)
        except ValueError:
            pass
        ents.append({"guid": a.get("url"), "link": a.get("url", ""), "title": a.get("title", ""), "summary": "",
                     "published": p, "raw": json.dumps(a, sort_keys=True), "lang": a.get("language", ""),
                     "extra": {"domain": a.get("domain"), "country": a.get("sourcecountry"), "query": qname}})
    new += store_items(con, "gdelt:" + qname, "global", GDELT_BASE, ents, fetched)
    # tone timeline (average tone, not article text)
    code, body = http_get(GDELT_BASE, params={"query": q, "mode": "timelinetone", "format": "json", "timespan": "1d"}, sleep=sleep)
    j = json.loads(body) if body.strip().startswith(b"{") else {}
    nf = 0
    for tl in j.get("timeline", []):
        for pt in tl.get("data", []):
            try:
                t = dt.datetime.strptime(pt["date"], "%Y%m%dT%H%M%SZ").replace(tzinfo=dt.timezone.utc)
                nf += store_feature(con, "gdelt_tone:" + qname, iso(t), pt["value"], fetched, GDELT_BASE, json.dumps(pt, sort_keys=True))
            except (KeyError, ValueError, TypeError):
                continue
    con.commit()
    log_fetch(con, "gdelt:" + qname, GDELT_BASE, True, 200, new + nf)
    return new + nf


def job_fng(con, sleep=time.sleep):
    url = "https://api.alternative.me/fng/"
    fetched = now_utc()
    code, body = http_get(url, params={"limit": 30}, sleep=sleep)
    j = json.loads(body)
    n = 0
    for d in j.get("data", []):
        t = dt.datetime.fromtimestamp(int(d["timestamp"]), dt.timezone.utc)
        n += store_feature(con, "fear_greed", iso(t), d["value"], fetched, url, json.dumps(d, sort_keys=True),
                           {"class": d.get("value_classification")})
    con.commit()
    log_fetch(con, "fng", url, True, 200, n)
    return n


def job_funding_oi(con, sleep=time.sleep):
    """Binance USDT-M futures PUBLIC market data (premiumIndex, openInterest). GET only, no key."""
    fetched = now_utc()
    bucket = iso(fetched.replace(second=0, microsecond=0, minute=fetched.minute - fetched.minute % 5))
    n = 0
    for sym in ("BTCUSDT", "ETHUSDT"):
        u1 = "https://fapi.binance.com/fapi/v1/premiumIndex"
        _, b1 = http_get(u1, params={"symbol": sym}, sleep=sleep)
        j1 = json.loads(b1)
        n += store_feature(con, "funding_rate:" + sym, bucket, j1["lastFundingRate"], fetched, u1, b1.decode(),
                           {"mark": j1.get("markPrice"), "index": j1.get("indexPrice")})
        u2 = "https://fapi.binance.com/fapi/v1/openInterest"
        _, b2 = http_get(u2, params={"symbol": sym}, sleep=sleep)
        j2 = json.loads(b2)
        n += store_feature(con, "open_interest:" + sym, bucket, j2["openInterest"], fetched, u2, b2.decode())
    con.commit()
    log_fetch(con, "binance_funding_oi", "fapi.binance.com", True, 200, n)
    return n


def _et_close_passed(bar_date, now):
    """US cash close is 20:00 (EDT) or 21:00 (EST) UTC; use 21:30 UTC so DST never leaks a partial bar."""
    return now >= dt.datetime.combine(bar_date, dt.time(21, 30), tzinfo=dt.timezone.utc)


def fetch_us_daily(sym, now=None, sleep=time.sleep):
    import pandas as pd
    now = now or now_utc()
    url = "https://query1.finance.yahoo.com/v8/finance/chart/" + sym
    _, body = http_get(url, params={"range": "5y", "interval": "1d", "events": "div,split"}, sleep=sleep)
    j = json.loads(body)
    res = (j.get("chart") or {}).get("result")
    if not res:
        raise FetchError("yahoo: no result for %s" % sym)
    r = res[0]
    q = r["indicators"]["quote"][0]
    adj = (r["indicators"].get("adjclose") or [{}])[0].get("adjclose")
    ts = pd.to_datetime(r["timestamp"], unit="s", utc=True)
    df = pd.DataFrame({"open": q["open"], "high": q["high"], "low": q["low"], "close": q["close"],
                       "volume": q["volume"]}, index=ts.normalize())
    if adj:
        f = pd.Series(adj, index=df.index) / df["close"]
        for c in ("open", "high", "low", "close"):
            df[c] = df[c] * f
    df = df.dropna()
    df = df[[_et_close_passed(d.date(), now) for d in df.index]]
    df.index.name = "ts"
    df = df[~df.index.duplicated()].astype(float)
    return df, url, body


def job_klines(con, sleep=time.sleep):
    """Keep the USDT-M perpetual klines used by the forward tracker current (public GET, incremental)."""
    from . import store
    n = 0
    for sym in ("BTC/USDT", "ETH/USDT"):
        for tf in ("5m", "15m", "1h", "4h"):
            try:
                n += store.update_incremental("binanceusdm", "binanceusdm", sym + ":USDT", sym, tf)
            except Exception as e:      # noqa: BLE001  one dataset failing must not stop the others
                log_fetch(con, "klines", sym + tf, False, getattr(e, "http", None), 0, "%s: %s" % (type(e).__name__, e))
    log_fetch(con, "klines", "binanceusdm", True, 200, n)
    return n


def job_us_daily(con, sleep=time.sleep):
    from . import store
    n = 0
    for sym in US_SYMBOLS:
        try:
            df, url, body = fetch_us_daily(sym, sleep=sleep)
            if len(df) > 200:
                store.save(df, "yahoo", "US (Yahoo chart API, split/div-adjusted OHLC)", sym, "1d",
                           note="unofficial free endpoint; personal research use; raw_sha256=" + sha(body)[:16])
                n += 1
        except Exception as e:       # one symbol failing must not stop the others
            log_fetch(con, "us_daily", sym, False, getattr(e, "http", None), 0, "%s: %s" % (type(e).__name__, e))
        sleep(2.0)
    log_fetch(con, "us_daily", "yahoo", n > 0, 200, n)
    return n


def ro_con():
    """Read-only connection for consumers (agent container mounts data/ read-only)."""
    return sqlite3.connect("file:%s?mode=ro" % DB, uri=True, timeout=30)


# ---------------------------------------------------------------- as-of access (no look-ahead)
def items_asof(con, asof, since_hours=24, markets=None, limit=200):
    """Items KNOWN at `asof` (UTC datetime): fetched_at <= asof and published_at <= asof, newest first."""
    a = iso(asof)
    lo = iso(asof - dt.timedelta(hours=since_hours))
    q = "SELECT id,source,market,link,title,summary,published_at,fetched_at,raw_sha256 FROM items " \
        "WHERE fetched_at<=? AND published_at<=? AND published_at>=?"
    args = [a, a, lo]
    if markets:
        q += " AND market IN (%s)" % ",".join("?" * len(markets))
        args += list(markets)
    q += " ORDER BY published_at DESC LIMIT ?"
    cur = con.execute(q, args + [limit])
    names = [d[0] for d in cur.description]
    return [dict(zip(names, r)) for r in cur.fetchall()]


def features_asof(con, asof, name_prefix=None, n_last=1):
    """Latest `n_last` observations per feature name with fetched_at <= asof AND ts <= asof."""
    a = iso(asof)
    q = "SELECT name,ts,value,fetched_at,source_url FROM features WHERE fetched_at<=? AND ts<=?"
    args = [a, a]
    if name_prefix:
        q += " AND name LIKE ?"
        args.append(name_prefix + "%")
    q += " ORDER BY name, ts DESC"
    out, cnt = [], {}
    for r in con.execute(q, args):
        cnt[r[0]] = cnt.get(r[0], 0) + 1
        if cnt[r[0]] <= n_last:
            out.append(dict(zip(("name", "ts", "value", "fetched_at", "source_url"), r)))
    return out


# ---------------------------------------------------------------- parquet snapshot + status
def export_parquet():
    import pandas as pd
    pq = NEWS_DIR / "parquet"
    pq.mkdir(exist_ok=True)
    con = db()
    for t in ("items", "features"):
        df = pd.read_sql_query("SELECT * FROM %s" % t, con)
        tmp = pq / (t + ".parquet.tmp")
        df.to_parquet(tmp)
        tmp.replace(pq / (t + ".parquet"))
    con.close()


def counts():
    if not DB.exists():
        return {}
    con = sqlite3.connect("file:%s?mode=ro" % DB, uri=True)
    out = {}
    for r in con.execute("SELECT source, COUNT(*), MIN(published_at), MAX(published_at), MAX(fetched_at) FROM items GROUP BY source"):
        out["items:" + r[0]] = {"n": r[1], "first_pub": r[2], "last_pub": r[3], "last_fetch": r[4]}
    for r in con.execute("SELECT name, COUNT(*), MIN(ts), MAX(ts) FROM features GROUP BY name"):
        out["feature:" + r[0]] = {"n": r[1], "first_ts": r[2], "last_ts": r[3]}
    con.close()
    return out


def write_status(obj):
    NEWS_DIR.mkdir(parents=True, exist_ok=True)
    tmp = STATUS.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, indent=1, default=str))
    tmp.replace(STATUS)


# ---------------------------------------------------------------- scheduler
def build_jobs():
    jobs = {}
    for s in RSS_SOURCES:
        jobs["rss:" + s["id"]] = dict(every=s["every"], fn=lambda con, s=s: job_rss(con, s))
    for i, q in enumerate(GDELT_QUERIES):
        jobs["gdelt:" + q] = dict(every=GDELT_EVERY, fn=lambda con, q=q: job_gdelt(con, q), offset=30 * i)
    jobs["fng"] = dict(every=6 * 3600, fn=job_fng)
    jobs["binance_funding_oi"] = dict(every=300, fn=job_funding_oi)
    jobs["klines"] = dict(every=1800, fn=job_klines, offset=60)
    jobs["us_daily"] = dict(every=6 * 3600, fn=job_us_daily, offset=120)
    jobs["retention"] = dict(every=24 * 3600, fn=lambda con: sum(__import__("tp.retention", fromlist=["x"]).prune_news(con).values()), offset=600)
    jobs["parquet_export"] = dict(every=3600, fn=lambda con: export_parquet(), offset=300)
    return jobs


def backoff_delay(fails, base, retry_after=None, rnd=random.random):
    d = min(3600, max(base, 30) * (2 ** min(fails, 8)))
    if retry_after:
        d = max(d, retry_after)
    return d * (0.8 + 0.4 * rnd())


def run_forever(stop=lambda: False, tick=2.0, clock=time.monotonic, sleep=time.sleep, jobs=None):
    jobs = jobs or build_jobs()
    con = db()
    t0 = clock()
    state = {k: {"due": t0 + j.get("offset", 0) + 5, "fails": 0, "last_ok": None, "last_err": None, "runs": 0}
             for k, j in jobs.items()}
    last_hb = 0.0
    while not stop():
        if clock() - last_hb > 30:                       # heartbeat independent of job cadence
            write_status({"updated": iso(now_utc()), "jobs": state})
            last_hb = clock()
        for k, j in jobs.items():
            st = state[k]
            if clock() < st["due"]:
                continue
            try:
                n = j["fn"](con)
                st.update(fails=0, last_ok=iso(now_utc()), last_new=n, last_err=None, runs=st["runs"] + 1,
                          due=clock() + j["every"] * (0.9 + 0.2 * random.random()))
            except Exception as e:      # noqa: BLE001  - any failure => backoff, never crash the daemon
                st["fails"] += 1
                st["last_err"] = "%s: %s" % (type(e).__name__, clean_text(e, 160))
                st["due"] = clock() + backoff_delay(st["fails"], j["every"], getattr(e, "retry_after", None))
                try:
                    log_fetch(con, k, "", False, getattr(e, "http", None), 0, st["last_err"])
                except Exception:       # noqa: BLE001
                    pass
            write_status({"updated": iso(now_utc()), "jobs": state})
        sleep(tick)
