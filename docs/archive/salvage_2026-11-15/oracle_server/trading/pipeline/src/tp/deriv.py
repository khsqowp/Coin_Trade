"""Binance USDT-M futures PUBLIC derivatives collector. No LLM, no API key, GET + public WebSocket only.

Sources (all documented public market-data endpoints; no signed/USER_DATA call, no order endpoint):
  * wss://fstream.binance.com/market/ws/!forceOrder@arr   public liquidation-order stream (BTCUSDT, ETHUSDT rows kept)
  * /futures/data/openInterestHist, globalLongShortAccountRatio, topLongShortPositionRatio, takerlongshortRatio
    (5m period; Binance only serves ~the last 30 days => we backfill 30d once and then keep accumulating)
  * /fapi/v1/fundingRate (history), /fapi/v1/premiumIndex + /fapi/v1/openInterest (spot-in-time, via news.py)
Storage: data/deriv/deriv.sqlite (journal_mode DELETE). Every table has fetched_at; raw rows keep sha256.
Liquidation stream history does NOT exist retroactively: it only accumulates from the moment this service runs.
"""
import asyncio
import datetime as dt
import hashlib
import json
import sqlite3
import time

import requests

from .config import DATA, scrub

DDIR = DATA / "deriv"
DB = DDIR / "deriv.sqlite"
STATUS = DDIR / "status.json"
SYMBOLS = ("BTCUSDT", "ETHUSDT")
FAPI = "https://fapi.binance.com"
WS_URL = "wss://fstream.binance.com/market/ws/!forceOrder@arr"
UA = "tp-research-collector/1.0 (non-commercial research; public endpoints, low rate)"
PERIOD = "5m"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS liq(ts_ms INTEGER, symbol TEXT, side TEXT, price REAL, avg_price REAL, qty REAL, status TEXT,
  fetched_at TEXT, raw_sha256 TEXT, PRIMARY KEY(ts_ms, symbol, side, qty, price));
CREATE TABLE IF NOT EXISTS oi_hist(symbol TEXT, ts_ms INTEGER, oi REAL, oi_value REAL, fetched_at TEXT, PRIMARY KEY(symbol, ts_ms));
CREATE TABLE IF NOT EXISTS ls_ratio(kind TEXT, symbol TEXT, ts_ms INTEGER, long_share REAL, short_share REAL, ratio REAL, fetched_at TEXT,
  PRIMARY KEY(kind, symbol, ts_ms));
CREATE TABLE IF NOT EXISTS taker(symbol TEXT, ts_ms INTEGER, buy_vol REAL, sell_vol REAL, ratio REAL, fetched_at TEXT, PRIMARY KEY(symbol, ts_ms));
CREATE TABLE IF NOT EXISTS funding_hist(symbol TEXT, ts_ms INTEGER, rate REAL, fetched_at TEXT, PRIMARY KEY(symbol, ts_ms));
"""


def now_iso():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def db():
    DDIR.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB, timeout=30)
    con.execute("PRAGMA journal_mode=DELETE")
    con.executescript(_SCHEMA)
    return con


def parse_force_order(msg):
    """Binance forceOrder event -> row tuple or None (other symbols / malformed are ignored)."""
    try:
        o = msg["o"]
        if msg.get("e") != "forceOrder" or o["s"] not in SYMBOLS:
            return None
        raw = hashlib.sha256(json.dumps(msg, sort_keys=True).encode()).hexdigest()
        return (int(o["T"]), o["s"], o["S"], float(o["p"]), float(o["ap"]), float(o["z"] or o["q"]), o["X"], now_iso(), raw)
    except (KeyError, TypeError, ValueError):
        return None


def save_liq(con, rows):
    con.executemany("INSERT OR IGNORE INTO liq VALUES (?,?,?,?,?,?,?,?,?)", rows)
    con.commit()


# ---------------------------------------------------------------- REST polling
_last = {"t": 0.0}


def get(path, params):
    w = _last["t"] + 0.6 - time.monotonic()
    if w > 0:
        time.sleep(w)
    r = requests.get(FAPI + path, params=params, headers={"User-Agent": UA}, timeout=20)
    _last["t"] = time.monotonic()
    if r.status_code in (418, 429):
        raise RuntimeError("rate limited HTTP %s retry-after=%s" % (r.status_code, r.headers.get("Retry-After")))
    r.raise_for_status()
    return r.json()


def _latest(con, table, sym, kind=None):
    q = "SELECT MAX(ts_ms) FROM %s WHERE symbol=?" % table
    a = [sym]
    if kind:
        q += " AND kind=?"
        a.append(kind)
    return con.execute(q, a).fetchone()[0]


def _first(con, table, sym, kind=None):
    q = "SELECT MIN(ts_ms) FROM %s WHERE symbol=?" % table
    a = [sym]
    if kind:
        q += " AND kind=?"
        a.append(kind)
    return con.execute(q, a).fetchone()[0]


def _walk(con, table, path, kind, sym, start, end, step, fa):
    added = 0
    while start < end - step:
        rows = get(path, {"symbol": sym, "period": PERIOD, "limit": 500, "startTime": start,
                          "endTime": min(end, start + 499 * step)})
        for r in rows:
            ts = int(r["timestamp"])
            if table == "oi_hist":
                con.execute("INSERT OR IGNORE INTO oi_hist VALUES (?,?,?,?,?)", (sym, ts, float(r["sumOpenInterest"]), float(r["sumOpenInterestValue"]), fa))
            elif table == "ls_ratio":
                ls = r.get("longAccount", r.get("longPosition"))
                ss = r.get("shortAccount", r.get("shortPosition"))
                con.execute("INSERT OR IGNORE INTO ls_ratio VALUES (?,?,?,?,?,?,?)", (kind, sym, ts, float(ls), float(ss), float(r["longShortRatio"]), fa))
            else:
                con.execute("INSERT OR IGNORE INTO taker VALUES (?,?,?,?,?,?)", (sym, ts, float(r["buyVol"]), float(r["sellVol"]), float(r["buySellRatio"]), fa))
            added += 1
        con.commit()
        start += 500 * step          # window-based paging: an empty/short window must not stop the walk
    return added


def poll_hist(con, sym, backfill_days=30, now_ms=None):
    """Incremental pull of 5m histories. Starts at last stored ts (or now-backfill_days). Returns rows added."""
    now_ms = now_ms or int(time.time() * 1000)
    fa, added = now_iso(), 0
    step = 5 * 60 * 1000
    specs = [("oi_hist", "/futures/data/openInterestHist", None),
             ("ls_ratio", "/futures/data/globalLongShortAccountRatio", "global_acct"),
             ("ls_ratio", "/futures/data/topLongShortPositionRatio", "top_pos"),
             ("taker", "/futures/data/takerlongshortRatio", None)]
    for table, path, kind in specs:
        last = _latest(con, table, sym, kind)
        first = _first(con, table, sym, kind)
        floor = now_ms - min(backfill_days, 28) * 86400_000
        ranges = []
        if first and first > floor + 2 * 3600_000:
            ranges.append((floor, first - step))             # one-off backward fill of the ~30d window
        ranges.append((max(last + step, floor) if last else floor, now_ms))
        for lo, hi in ranges:
            added += _walk(con, table, path, kind, sym, lo, hi, step, fa)
    # funding history (8h)
    last = _latest(con, "funding_hist", sym)
    rows = get("/fapi/v1/fundingRate", {"symbol": sym, "limit": 1000, **({"startTime": last + 1} if last else {})})
    for r in rows:
        con.execute("INSERT OR IGNORE INTO funding_hist VALUES (?,?,?,?)", (sym, int(r["fundingTime"]), float(r["fundingRate"]), fa))
    con.commit()
    return added + len(rows)


# ---------------------------------------------------------------- service
async def ws_loop(state, stop):
    import aiohttp
    fails = 0
    con = db()
    while not stop():
        try:
            async with aiohttp.ClientSession(headers={"User-Agent": UA}) as s:
                async with s.ws_connect(WS_URL, heartbeat=30, receive_timeout=120, max_msg_size=1_000_000) as ws:
                    state["ws"] = {"connected_at": now_iso(), "msgs": 0, "kept": 0}
                    fails = 0
                    buf, last_flush = [], time.monotonic()
                    while not stop():
                        try:
                            m = await ws.receive(timeout=20)
                        except asyncio.TimeoutError:
                            m = None
                        if m is not None:
                            if m.type == aiohttp.WSMsgType.TEXT:
                                state["ws"]["msgs"] += 1
                                try:
                                    row = parse_force_order(json.loads(m.data))
                                except ValueError:
                                    row = None
                                if row:
                                    buf.append(row)
                            elif m.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR, aiohttp.WSMsgType.CLOSING):
                                break
                        if buf and time.monotonic() - last_flush > 5:
                            save_liq(con, buf)
                            state["ws"]["kept"] += len(buf)
                            state["ws"]["last_liq_saved"] = now_iso()
                            buf, last_flush = [], time.monotonic()
                        state["ws"]["heartbeat"] = now_iso()
                    if buf:
                        save_liq(con, buf)
        except Exception as e:      # noqa: BLE001
            fails += 1
            state["ws_error"] = {"at": now_iso(), "msg": scrub(e, 150), "fails": fails}
        await asyncio.sleep(min(600, 5 * 2 ** min(fails, 7)))     # 24h forced disconnects reconnect here too


def _poll_sym(sym):
    con = db()                      # sqlite connections are per-thread
    try:
        return poll_hist(con, sym)
    finally:
        con.close()


async def rest_loop(state, stop, every=900):
    fails = 0
    while not stop():
        try:
            for sym in SYMBOLS:
                n = await asyncio.get_running_loop().run_in_executor(None, _poll_sym, sym)
                state.setdefault("rest", {})[sym] = {"last_ok": now_iso(), "rows_added": n}
            fails = 0
            delay = every
        except Exception as e:      # noqa: BLE001
            fails += 1
            state["rest_error"] = {"at": now_iso(), "msg": scrub(e, 150), "fails": fails}
            delay = min(3600, 60 * 2 ** min(fails, 6))
        for _ in range(int(delay // 5)):
            if stop():
                return
            await asyncio.sleep(5)


async def status_loop(state, stop):
    while not stop():
        state["updated"] = now_iso()
        STATUS.parent.mkdir(parents=True, exist_ok=True)
        tmp = STATUS.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, indent=1, default=str))
        tmp.replace(STATUS)
        await asyncio.sleep(15)


def run_forever(stop=lambda: False):
    state = {"started": now_iso(), "symbols": SYMBOLS}

    async def main():
        await asyncio.gather(ws_loop(state, stop), rest_loop(state, stop), status_loop(state, stop))
    asyncio.run(main())


def counts():
    if not DB.exists():
        return {}
    con = sqlite3.connect("file:%s?mode=ro" % DB, uri=True)
    out = {}
    out["liq"] = con.execute("SELECT COUNT(*), MIN(ts_ms), MAX(ts_ms) FROM liq").fetchone()
    out["oi_hist"] = con.execute("SELECT COUNT(*), MIN(ts_ms), MAX(ts_ms) FROM oi_hist").fetchone()
    out["ls_ratio"] = con.execute("SELECT COUNT(*), MIN(ts_ms), MAX(ts_ms) FROM ls_ratio").fetchone()
    out["taker"] = con.execute("SELECT COUNT(*), MIN(ts_ms), MAX(ts_ms) FROM taker").fetchone()
    out["funding_hist"] = con.execute("SELECT COUNT(*), MIN(ts_ms), MAX(ts_ms) FROM funding_hist").fetchone()
    con.close()
    f = lambda ms: dt.datetime.fromtimestamp(ms / 1000, dt.timezone.utc).strftime("%Y-%m-%d %H:%M") if ms else None
    return {k: {"n": v[0], "first": f(v[1]), "last": f(v[2])} for k, v in out.items()}


def backfill_funding(con, sym, years=3):
    """One-off public history of the 8h funding rate (the collector only keeps the latest 1000 per call). INSERT OR IGNORE."""
    fa = now_iso()
    start = int((time.time() - years * 365 * 86400) * 1000)
    n = 0
    while True:
        rows = get("/fapi/v1/fundingRate", {"symbol": sym, "limit": 1000, "startTime": start})
        if not rows:
            break
        for r in rows:
            con.execute("INSERT OR IGNORE INTO funding_hist VALUES (?,?,?,?)", (sym, int(r["fundingTime"]), float(r["fundingRate"]), fa))
            n += 1
        con.commit()
        nxt = int(rows[-1]["fundingTime"]) + 1
        if nxt <= start or len(rows) < 1000:
            break
        start = nxt
    return n
