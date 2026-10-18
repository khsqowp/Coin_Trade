"""Whitelisted-host fetcher for the map_api research (data.binance.vision, llama, coingecko, alternative.me, deribit).
Serial, throttled per host, exponential backoff, STOP on 418/429/403 (writes STOP file). Cache: .rs_cache/online/.
usage: python -m app.rs_map_api_fetch vision|llama|gecko|misc
"""
from __future__ import annotations
import datetime as dt, json, os, sys, time, urllib.request, urllib.error, urllib.parse

ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".rs_cache", "online")
ALLOWED = {"data.binance.vision", "api.llama.fi", "api.coingecko.com", "api.alternative.me", "www.deribit.com"}
STOP = os.path.join(ROOT, "STOP")
UA = "Mozilla/5.0 (research-bulk-download; polite)"
_last = {}


class Stop(Exception):
    pass


def get(url: str, interval: float, binary=False, tries=4):
    host = urllib.parse.urlparse(url).netloc
    assert host in ALLOWED, host
    if os.path.exists(STOP):
        raise Stop("STOP file present")
    wait = interval - (time.time() - _last.get(host, 0))
    if wait > 0:
        time.sleep(wait)
    delay = 3.0
    for k in range(tries):
        _last[host] = time.time()
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=40) as r:
                b = r.read()
            return b if binary else b.decode()
        except urllib.error.HTTPError as e:
            if e.code in (418, 429, 403):
                open(STOP, "w").write(f"{e.code} {url}\n")
                raise Stop(f"HTTP {e.code} {url}")
            if e.code == 404:
                return None
            if e.code >= 500 and k < tries - 1:
                time.sleep(delay); delay *= 2; continue
            raise
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            if k == tries - 1:
                raise
            time.sleep(delay); delay *= 2


def save(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)


def fetch_file(url, path, interval=1.05):
    if os.path.exists(path) or os.path.exists(path + ".404"):
        return "have"
    b = get(url, interval, binary=True)
    if b is None:
        save(path + ".404", b""); return "404"
    save(path, b); return "ok"


V = "https://data.binance.vision/data/futures/um"
PREM_SYMS = ["BTC", "ETH", "BNB", "SOL", "XRP", "ADA", "DOGE", "LINK", "AVAX", "LTC", "DOT", "TRX", "ATOM", "UNI",
             "NEAR", "FIL", "APT", "ARB", "OP", "INJ"]
MET_SYMS = ["BTC", "ETH", "BNB", "SOL", "XRP", "ADA", "DOGE", "LINK", "AVAX", "LTC"]


def run_vision():
    cnt = {}
    # phase A: premiumIndexKlines 1d (monthly 2022-01..2026-09, daily for 2026-10)
    months = [f"{y}-{m:02d}" for y in range(2022, 2027) for m in range(1, 13) if (y, m) <= (2026, 9)]
    for s in PREM_SYMS:
        sym = s + "USDT"
        for ym in months:
            st = fetch_file(f"{V}/monthly/premiumIndexKlines/{sym}/1d/{sym}-1d-{ym}.zip",
                            f"{ROOT}/premium/{sym}-1d-{ym}.zip")
            cnt[st] = cnt.get(st, 0) + 1
        for d in range(1, 13):
            ds = f"2026-10-{d:02d}"
            st = fetch_file(f"{V}/daily/premiumIndexKlines/{sym}/1d/{sym}-1d-{ds}.zip",
                            f"{ROOT}/premium/{sym}-1d-{ds}.zip")
            cnt[st] = cnt.get(st, 0) + 1
        print("premium", sym, cnt, flush=True)
    # phase B: metrics, day-major newest first
    day = dt.date(2026, 10, 12)
    end = dt.date(2022, 1, 1)
    n = 0
    while day >= end:
        for s in MET_SYMS:
            sym = s + "USDT"
            st = fetch_file(f"{V}/daily/metrics/{sym}/{sym}-metrics-{day}.zip", f"{ROOT}/metrics/{sym}-{day}.zip")
            cnt[st] = cnt.get(st, 0) + 1
            n += 1
        if day.day == 1:
            print("metrics", day, cnt, flush=True)
        day -= dt.timedelta(days=1)


def run_llama():
    iv = 1.05
    out = f"{ROOT}/defillama"
    for name, url in [("protocols", "https://api.llama.fi/protocols"), ("chains", "https://api.llama.fi/v2/chains"),
                      ("hist_all", "https://api.llama.fi/v2/historicalChainTvl")]:
        p = f"{out}/{name}.json"
        if not os.path.exists(p):
            b = get(url, iv, binary=True); save(p, b or b"null")
    for ch in ["Ethereum", "Solana", "BSC", "Tron", "Avalanche", "Arbitrum", "Optimism", "Polygon", "Sui", "Aptos",
               "Near", "Cardano", "Cosmos", "Polkadot", "Algorand", "Hedera", "Injective", "Ton", "Base", "Fantom",
               "Stellar", "Bitcoin", "Litecoin", "Dogecoin", "Ripple", "Internet Computer", "Starknet"]:
        p = f"{out}/chain_{ch.replace(' ', '_')}.json"
        if not os.path.exists(p):
            b = get(f"https://api.llama.fi/v2/historicalChainTvl/{urllib.parse.quote(ch)}", iv, binary=True)
            save(p, b or b"null")
    prots = json.load(open(f"{out}/protocols.json"))
    # protocol-level TVL for tokens in our universe (by listed symbol)
    uni = set(json.load(open(f"{ROOT}/misc/universe.json")))
    best = {}
    for pr in prots:
        sy = (pr.get("symbol") or "").upper()
        if sy in uni and (sy not in best or (pr.get("tvl") or 0) > (best[sy].get("tvl") or 0)):
            best[sy] = pr
    json.dump({k: v["slug"] for k, v in best.items()}, open(f"{out}/proto_map.json", "w"))
    for sy, pr in best.items():
        p = f"{out}/proto_{pr['slug']}.json"
        if not os.path.exists(p):
            b = get(f"https://api.llama.fi/protocol/{pr['slug']}", iv, binary=True)
            save(p, b or b"null")
        print("llama", sy, pr["slug"], flush=True)


def run_gecko():
    iv = 2.2
    out = f"{ROOT}/coingecko"
    uni = json.load(open(f"{ROOT}/misc/universe.json"))
    ids = {}
    for page in (1, 2, 3):
        p = f"{out}/markets_{page}.json"
        if not os.path.exists(p):
            b = get(f"https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=250&page={page}", iv, binary=True)
            save(p, b or b"[]")
        for c in json.load(open(p)):
            sy = c["symbol"].upper()
            if sy in uni and sy not in ids:
                ids[sy] = c["id"]
    json.dump(ids, open(f"{out}/ids.json", "w"))
    cats = {}
    for sy, cid in ids.items():
        p = f"{out}/coin_{cid}.json"
        if not os.path.exists(p):
            b = get(f"https://api.coingecko.com/api/v3/coins/{cid}?localization=false&tickers=false&market_data=false&community_data=false&developer_data=false&sparkline=false", iv, binary=True)
            save(p, b or b"{}")
        d = json.load(open(p))
        cats[sy] = d.get("categories") or []
        print("gecko", sy, len(cats[sy]), flush=True)
    json.dump(cats, open(f"{out}/categories.json", "w"))


def run_misc():
    out = f"{ROOT}/misc"
    p = f"{out}/fng.json"
    if not os.path.exists(p):
        save(p, get("https://api.alternative.me/fng/?limit=0&format=json", 1.5, binary=True) or b"null")
    # Deribit DVOL (BTC, ETH), 1D resolution, chunks of ~1000 days
    for cur in ("BTC", "ETH"):
        rows = []
        t0 = int(dt.datetime(2021, 3, 1).timestamp() * 1000)
        t1 = int(time.time() * 1000)
        step = 900 * 86400 * 1000
        a = t0
        while a < t1:
            b = min(a + step, t1)
            u = (f"https://www.deribit.com/api/v2/public/get_volatility_index_data?currency={cur}"
                 f"&start_timestamp={a}&end_timestamp={b}&resolution=1D")
            r = get(u, 1.5)
            if r:
                rows += json.loads(r).get("result", {}).get("data", [])
            a = b
        save(f"{out}/dvol_{cur}.json", json.dumps(rows).encode())
        print("dvol", cur, len(rows), flush=True)


if __name__ == "__main__":
    os.makedirs(ROOT, exist_ok=True)
    mode = sys.argv[1]
    if mode == "vision":
        run_vision()
    else:
        os.makedirs(f"{ROOT}/misc", exist_ok=True)
        if mode == "misc":
            run_misc()
        elif mode == "llama":
            run_llama()
        elif mode == "gecko":
            run_gecko()
