"""Round 3 data: universe + exchange filters from PUBLIC Binance USDT-M endpoints (GET only, low rate, no key) and 1h klines / funding for the universe."""
import datetime as dt
import json
import os
import time

import requests

from . import deriv, store
from .config import DATA

FAPI = "https://fapi.binance.com"
UNIVERSE = DATA / "research" / "rot_universe.json"
UA = "tp-research-collector/1.0"
N_TOP = 25
ALWAYS = ("BTCUSDT", "ETHUSDT")
DAYS = 730


def _get(path, params=None):
    time.sleep(0.6)
    r = requests.get(FAPI + path, params=params, headers={"User-Agent": UA}, timeout=20)
    r.raise_for_status()
    return r.json()


def filters_of(s):
    f = {x["filterType"]: x for x in s["filters"]}
    mn = f.get("MIN_NOTIONAL", {}).get("notional")
    ml = f.get("MARKET_LOT_SIZE") or f.get("LOT_SIZE")
    return {"minNotional": float(mn) if mn else 5.0, "stepSize": float(ml["stepSize"]), "minQty": float(ml["minQty"]),
            "maxQty": float(ml["maxQty"]), "tickSize": float(f["PRICE_FILTER"]["tickSize"])}


def build_universe():
    info = _get("/fapi/v1/exchangeInfo")
    tick = {t["symbol"]: float(t["quoteVolume"]) for t in _get("/fapi/v1/ticker/24hr")}
    ok = {s["symbol"]: s for s in info["symbols"] if s.get("contractType") == "PERPETUAL" and s["status"] == "TRADING" and s["quoteAsset"] == "USDT"
          and s["symbol"].isascii() and "_" not in s["symbol"]}
    ranked = sorted(ok, key=lambda k: -tick.get(k, 0.0))
    pick = list(ALWAYS) + [k for k in ranked if k not in ALWAYS][:N_TOP - len(ALWAYS) + 0]
    pick = pick[:N_TOP + len(ALWAYS)] if len(pick) > N_TOP + len(ALWAYS) else pick
    syms = {}
    for k in pick:
        s = ok[k]
        syms[k] = dict(base=s["baseAsset"], onboard=dt.datetime.fromtimestamp(s["onboardDate"] / 1000, dt.timezone.utc).strftime("%Y-%m-%d"),
                       quote_volume_24h=tick.get(k, 0.0), **filters_of(s))
    out = {"fetched_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "sources": [FAPI + "/fapi/v1/exchangeInfo", FAPI + "/fapi/v1/ticker/24hr"],
           "note": "top USDT perpetuals by 24h quote volume at fetch time; filters assumed constant over history (limitation); survivorship bias: delisted symbols absent",
           "symbols": syms}
    UNIVERSE.parent.mkdir(parents=True, exist_ok=True)
    UNIVERSE.write_text(json.dumps(out, indent=1, sort_keys=True))
    return out


def fetch_all(log=print):
    os.nice(10)
    u = build_universe()
    con = deriv.db()
    now = dt.datetime.now(dt.timezone.utc)
    rows = []
    for k, v in u["symbols"].items():
        sym = "%s/USDT" % v["base"]
        try:
            df, ex = store.fetch_binance("%s/USDT:USDT" % v["base"], "1h", now - dt.timedelta(days=DAYS), max_pages=30, exchange="binanceusdm")
            store.save(df, "binanceusdm", ex, sym, "1h", note="USDT-M perpetual last-price OHLCV via ccxt, closed candles only")
            nf = deriv.backfill_funding(con, k, years=2.1)
            rows.append({"symbol": k, "rows": len(df), "first": str(df.index[0]), "funding_rows": nf})
            log(rows[-1])
        except Exception as e:      # noqa: BLE001  one symbol failing must not stop the others
            rows.append({"symbol": k, "error": "%s: %s" % (type(e).__name__, str(e)[:100])})
            log(rows[-1])
        time.sleep(0.5)
    return {"universe_n": len(u["symbols"]), "results": rows}
