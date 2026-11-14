"""Hyperliquid READ-ONLY public-data collector (BTC/ETH perp positions -> liquidation prices). No key, no signing, no orders.

Legitimate data path (official docs https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api):
  * There is NO official endpoint listing all accounts. We do NOT scrape indexers or guess addresses.
  * Official public WebSocket `trades` feed includes `users: [buyer, seller]` for every trade => we discover
    addresses that actually traded BTC/ETH perps with notional >= MIN_NOTIONAL (a *sample*, biased to active traders).
  * Official info request `clearinghouseState` (public, per address, weight 2) returns each open position with
    `liquidationPx`, entryPx, szi, positionValue, leverage. We poll only discovered addresses.
Rate limits (docs, per IP): 1200 weight/min REST; WS: 10 connections, 1000 subscriptions. We stay at <= ~25% (HL_MAX_WEIGHT_MIN).
Only `info` POSTs and one WS `subscribe` are ever sent. The `exchange` endpoint is never referenced.
Terms: https://app.hyperliquid.xyz/terms is a JS page (not machine readable here); the API docs publish the public
read-only API and its limits for developers. Owner should read the ToS; usage is low-rate, non-commercial research.
"""
import asyncio
import datetime as dt
import hashlib
import json
import sqlite3
import time

import requests

from .config import DATA, scrub

HDIR = DATA / "hl"
DB = HDIR / "hl.sqlite"
STATUS = HDIR / "status.json"
INFO = "https://api.hyperliquid.xyz/info"
WS = "wss://api.hyperliquid.xyz/ws"
COINS = ("BTC", "ETH")
MIN_NOTIONAL = 25_000.0
MAX_ADDRS = 6000
MAX_WEIGHT_MIN = 300            # of the documented 1200/min per IP
UA = "tp-research-collector/1.0 (non-commercial research; read-only public info API)"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS addrs(addr TEXT PRIMARY KEY, first_seen TEXT, last_seen TEXT, best_notional REAL,
  last_checked TEXT, n_checks INTEGER DEFAULT 0, has_pos INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS positions(snap_ts TEXT, addr TEXT, coin TEXT, szi REAL, entry_px REAL, liq_px REAL,
  pos_value REAL, leverage REAL, lev_type TEXT, margin REAL, acct_value REAL, raw_sha256 TEXT);
CREATE INDEX IF NOT EXISTS ix_pos ON positions(coin, snap_ts);
CREATE TABLE IF NOT EXISTS market(snap_ts TEXT, coin TEXT, mid REAL, open_interest REAL, funding REAL);
"""


def now_iso():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def db():
    HDIR.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB, timeout=30)
    con.execute("PRAGMA journal_mode=DELETE")
    con.executescript(_SCHEMA)
    return con


# ---------------------------------------------------------------- REST (info only)
_last = {"t": 0.0}
WEIGHT = {"n": 0, "win": 0.0}


def info(payload, weight=2):
    if payload.get("type") not in ("clearinghouseState", "metaAndAssetCtxs", "allMids"):
        raise RuntimeError("info type not allowed in this read-only module")
    now = time.monotonic()
    if now - WEIGHT["win"] > 60:
        WEIGHT.update(n=0, win=now)
    if WEIGHT["n"] + weight > MAX_WEIGHT_MIN:
        time.sleep(max(0.0, 60 - (now - WEIGHT["win"])) + 0.5)
        WEIGHT.update(n=0, win=time.monotonic())
    gap = _last["t"] + 0.25 - time.monotonic()
    if gap > 0:
        time.sleep(gap)
    r = requests.post(INFO, json=payload, headers={"User-Agent": UA}, timeout=20)
    _last["t"] = time.monotonic()
    WEIGHT["n"] += weight
    if r.status_code == 429:
        raise RuntimeError("HTTP 429 rate limited")
    r.raise_for_status()
    return r.json(), r.content


def parse_state(addr, j, raw):
    """clearinghouseState -> list of position rows for COINS (validated; bad rows dropped)."""
    out = []
    acct = None
    try:
        acct = float(j["marginSummary"]["accountValue"])
    except (KeyError, TypeError, ValueError):
        pass
    h = hashlib.sha256(raw).hexdigest()
    for ap in j.get("assetPositions", []):
        p = ap.get("position", {})
        if p.get("coin") not in COINS:
            continue
        try:
            szi, entry = float(p["szi"]), float(p["entryPx"])
            liq = float(p["liquidationPx"]) if p.get("liquidationPx") not in (None, "") else None
            val = abs(float(p["positionValue"]))
            lev = float(p["leverage"]["value"])
        except (KeyError, TypeError, ValueError):
            continue
        if szi == 0 or not (entry > 0) or val <= 0 or lev <= 0 or lev > 200:
            continue
        out.append((p["coin"], szi, entry, liq, val, lev, p["leverage"].get("type"), float(p.get("marginUsed") or 0), acct, h))
    return out


def poll_market(con):
    (meta, ctxs), _ = info({"type": "metaAndAssetCtxs"}, weight=20)
    ts = now_iso()
    for m, c in zip(meta["universe"], ctxs):
        if m["name"] in COINS:
            con.execute("INSERT INTO market VALUES (?,?,?,?,?)", (ts, m["name"], float(c["midPx"]), float(c["openInterest"]), float(c["funding"])))
    con.commit()


def check_addr(con, addr):
    j, raw = info({"type": "clearinghouseState", "user": addr})
    rows = parse_state(addr, j, raw)
    ts = now_iso()
    for r in rows:
        con.execute("INSERT INTO positions VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", (ts, addr) + r[:7] + (r[7], r[8], r[9]))
    con.execute("UPDATE addrs SET last_checked=?, n_checks=n_checks+1, has_pos=? WHERE addr=?", (ts, int(bool(rows)), addr))
    con.commit()
    return len(rows)


def next_batch(con, n=20, now=None):
    """Priority: never-checked first, then holders by staleness (>10 min), then non-holders (>6 h)."""
    now = now or dt.datetime.now(dt.timezone.utc)
    t10 = (now - dt.timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
    t6h = (now - dt.timedelta(hours=6)).strftime("%Y-%m-%dT%H:%M:%SZ")
    q = """SELECT addr FROM addrs WHERE last_checked IS NULL
           UNION ALL SELECT addr FROM (SELECT addr FROM addrs WHERE has_pos=1 AND last_checked<? ORDER BY last_checked LIMIT ?)
           UNION ALL SELECT addr FROM (SELECT addr FROM addrs WHERE has_pos=0 AND last_checked<? ORDER BY last_checked LIMIT ?)"""
    return [r[0] for r in con.execute(q, (t10, n, t6h, n)).fetchall()][:n]


def add_addrs(con, trades):
    new = 0
    ts = now_iso()
    for t in trades:
        try:
            if t["coin"] not in COINS:
                continue
            notional = float(t["px"]) * float(t["sz"])
            if notional < MIN_NOTIONAL:
                continue
            for a in t.get("users", []):
                if not (isinstance(a, str) and len(a) == 42 and a.startswith("0x")):
                    continue
                cur = con.execute("INSERT OR IGNORE INTO addrs(addr,first_seen,last_seen,best_notional) VALUES (?,?,?,?)", (a, ts, ts, notional))
                if cur.rowcount:
                    new += 1
                else:
                    con.execute("UPDATE addrs SET last_seen=?, best_notional=MAX(best_notional,?) WHERE addr=?", (ts, notional, a))
        except (KeyError, TypeError, ValueError):
            continue
    con.commit()
    n = con.execute("SELECT COUNT(*) FROM addrs").fetchone()[0]
    if n > MAX_ADDRS:       # prune stale non-holders (never holders)
        con.execute("DELETE FROM addrs WHERE addr IN (SELECT addr FROM addrs WHERE has_pos=0 AND n_checks>=2 ORDER BY last_seen LIMIT ?)", (n - MAX_ADDRS,))
        con.commit()
    return new


# ---------------------------------------------------------------- service
async def ws_loop(state, stop):
    import aiohttp
    con = db()
    fails = 0
    while not stop():
        try:
            async with aiohttp.ClientSession(headers={"User-Agent": UA}) as s:
                async with s.ws_connect(WS, heartbeat=30, max_msg_size=2_000_000) as ws:
                    for c in COINS:
                        await ws.send_json({"method": "subscribe", "subscription": {"type": "trades", "coin": c}})
                    state["ws"] = {"connected_at": now_iso(), "trades": 0, "new_addrs": 0}
                    fails = 0
                    while not stop():
                        try:
                            m = await ws.receive(timeout=30)
                        except asyncio.TimeoutError:
                            await ws.send_json({"method": "ping"})
                            continue
                        if m.type != aiohttp.WSMsgType.TEXT:
                            break
                        try:
                            msg = json.loads(m.data)
                        except ValueError:
                            continue
                        if msg.get("channel") == "trades" and isinstance(msg.get("data"), list):
                            state["ws"]["trades"] += len(msg["data"])
                            state["ws"]["new_addrs"] += add_addrs(con, msg["data"])
                            state["ws"]["heartbeat"] = now_iso()
        except Exception as e:      # noqa: BLE001
            fails += 1
            state["ws_error"] = {"at": now_iso(), "msg": scrub(e, 150), "fails": fails}
        await asyncio.sleep(min(300, 5 * 2 ** min(fails, 6)))


def _poll_once():
    con = db()
    try:
        done = 0
        if int(time.time()) % 300 < 20:
            poll_market(con)
        for a in next_batch(con, 30):
            check_addr(con, a)
            done += 1
        return done
    finally:
        con.close()


def _thin_once():
    from . import retention
    con = db()
    try:
        return retention.thin_hl(con)
    finally:
        con.close()


async def poll_loop(state, stop):
    fails = 0
    last_thin = 0.0
    while not stop():
        try:
            n = await asyncio.get_running_loop().run_in_executor(None, _poll_once)
            state["poll"] = {"last_ok": now_iso(), "checked_last_batch": n}
            if time.time() - last_thin > 6 * 3600:
                state["retention"] = await asyncio.get_running_loop().run_in_executor(None, _thin_once)
                last_thin = time.time()
            fails = 0
            await asyncio.sleep(2 if n else 15)
        except Exception as e:      # noqa: BLE001
            fails += 1
            state["poll_error"] = {"at": now_iso(), "msg": scrub(e, 150), "fails": fails}
            await asyncio.sleep(min(600, 20 * 2 ** min(fails, 5)))


async def status_loop(state, stop):
    while not stop():
        state["updated"] = now_iso()
        HDIR.mkdir(parents=True, exist_ok=True)
        tmp = STATUS.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, indent=1, default=str))
        tmp.replace(STATUS)
        await asyncio.sleep(15)


def run_forever(stop=lambda: False):
    state = {"started": now_iso(), "coins": COINS}

    async def main():
        await asyncio.gather(ws_loop(state, stop), poll_loop(state, stop), status_loop(state, stop))
    asyncio.run(main())


def latest_positions(con, coin, asof_iso, max_age_min=25):
    """Latest snapshot per address with snap_ts <= asof (and not older than max_age_min before asof)."""
    lo = (dt.datetime.strptime(asof_iso, "%Y-%m-%dT%H:%M:%SZ") - dt.timedelta(minutes=max_age_min)).strftime("%Y-%m-%dT%H:%M:%SZ")
    q = """SELECT p.addr,p.szi,p.entry_px,p.liq_px,p.pos_value,p.leverage,p.snap_ts FROM positions p
           JOIN (SELECT addr, MAX(snap_ts) m FROM positions WHERE coin=? AND snap_ts<=? GROUP BY addr) x
             ON p.addr=x.addr AND p.snap_ts=x.m WHERE p.coin=? AND p.snap_ts>=?"""
    return con.execute(q, (coin, asof_iso, coin, lo)).fetchall()
