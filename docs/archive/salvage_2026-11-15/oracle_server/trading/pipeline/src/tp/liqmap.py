"""Liquidation-concentration estimates in ONE common format, from two independent legitimate public sources.

Common output ("price-band liquidation concentration"): bands of 0.5% relative to a reference price from -15% to +15%:
  {"source", "coin", "asof", "ref_price", "bands":[{"lo_pct","hi_pct","long_usd","short_usd"}], "summary":{...}, "meta":{...}}
  long_usd  = notional of LONG positions estimated to be liquidated if price trades into that band (bands below price)
  short_usd = same for SHORT positions (bands above price).

(2) binance_proxy  - ESTIMATE from Binance public OI history (5m), long/short ratio and klines (see assumptions below).
(3) hl_map         - MEASURED sample of Hyperliquid positions (public clearinghouseState liquidationPx) of addresses discovered
                     through the official public trades feed. A biased sample (active large traders), not the whole exchange.

ASSUMPTIONS / LIMITS of the Binance proxy (also in the docs and report):
  * We do not know the real leverage distribution nor any user's entry; each OI increase (per 5m bar, in USD) is assumed to
    open equal long and short notional at the bar's close price, split over leverages 5/10/20/50/100x with fixed weights
    (.35/.30/.20/.10/.05), tilted toward higher leverage on the crowded side using the global long/short account ratio.
  * OI decreases close existing positions proportionally across all levels (FIFO/LIFO unknown).
  * A level is cleared when the bar's low (longs) / high (shorts) trades through it (assumed liquidated).
  * Maintenance margin fixed at 0.5%; isolated-margin liquidation price formula p*(1-1/L+mmr) / p*(1+1/L-mmr); cross margin and
    portfolio margining are ignored. Positions opened before the OI history starts (<=28 days) are invisible, so early
    estimates are biased low. Treat as a rough SHAPE indicator, NOT a measurement.
Everything is deterministic and causal (a band at time t uses only OI/price data stamped <= t)."""
import datetime as dt
import math
import sqlite3

import numpy as np
import pandas as pd

from . import deriv, hl, store
from .config import DATA

STEP = 0.0025                       # internal grid: 0.25% in log-price
LN = math.log(1 + STEP)
LEVS = np.array([5, 10, 20, 50, 100], float)
W = np.array([.35, .30, .20, .10, .05])
MMR = 0.005
BAND_PCT = 0.5
RANGE_PCT = 15.0
MIN_DAYS_VALID = 90


def _ro(path):
    return sqlite3.connect("file:%s?mode=ro" % path, uri=True, timeout=30)


def accumulated_days():
    """Days of derivative history available (OI history span; liquidation stream accumulates from collector start)."""
    if not deriv.DB.exists():
        return 0.0
    con = _ro(deriv.DB)
    a, b = con.execute("SELECT MIN(ts_ms), MAX(ts_ms) FROM oi_hist").fetchone()
    con.close()
    return 0.0 if a is None else (b - a) / 86_400_000


def _gi(p, base):
    return int(round(math.log(p / base) / LN))


def proxy_series(oi_value, ls_long_share, k5, return_last_map=False):
    """oi_value: Series (USD, index UTC 5m, OI-hist timestamps shifted to availability time). ls_long_share: Series same index.
    k5: DataFrame of 5m klines with open/high/low/close indexed by bar OPEN time (bar closes at index+5m).
    Returns DataFrame[liq_imb, liq_dist_up_pct, liq_dist_dn_pct, long_below_usd, short_above_usd] indexed by availability time,
    and (optionally) the final (long_mass, short_mass, base_price) arrays."""
    idx = oi_value.index
    k = k5.reindex(idx - pd.Timedelta("5min"))        # bar that closes at the availability time
    hi, lo, cl = k["high"].values, k["low"].values, k["close"].values
    oi = oi_value.values.astype(float)
    share = ls_long_share.reindex(idx).ffill().fillna(0.5).values
    base = float(cl[np.nonzero(cl == cl)[0][0]])        # grid origin = FIRST valid close (using the sample median would leak the future)
    size = 4000
    off = size // 2
    longm, shortm = np.zeros(size), np.zeros(size)
    rows = []
    for t in range(len(idx)):
        if not (cl[t] == cl[t] and oi[t] == oi[t]):
            rows.append((np.nan,) * 5)
            continue
        # 1) liquidation sweep by this bar's range
        gl, gh = _gi(lo[t], base) + off, _gi(hi[t], base) + off
        if gl < size:
            longm[max(gl, 0):] = 0.0          # longs whose liquidation price >= bar low were liquidated
        if gh >= 0:
            shortm[:min(gh + 1, size)] = 0.0  # shorts whose liquidation price <= bar high were liquidated
        # 2) OI change
        if t > 0 and oi[t - 1] == oi[t - 1]:
            d = oi[t] - oi[t - 1]
            if d < 0 and oi[t - 1] > 0:
                f = max(0.0, 1.0 + d / oi[t - 1])
                longm *= f
                shortm *= f
            elif d > 0:
                p = cl[t]
                crowd = (share[t] - 0.5) * 2.0                       # >0: longs crowded
                for side, mass in (("long", longm), ("short", shortm)):
                    tilt = crowd if side == "long" else -crowd
                    w = W * (1.0 + np.where(LEVS >= 20, 0.5 * tilt, -0.5 * tilt))
                    w = np.clip(w, 1e-6, None)
                    w = w / w.sum()
                    for L, wl in zip(LEVS, w):
                        lp = p * (1 - 1 / L + MMR) if side == "long" else p * (1 + 1 / L - MMR)
                        gi = _gi(lp, base) + off
                        if 0 <= gi < size:
                            mass[gi] += d * wl
        # 3) summary at the current price
        pc = _gi(cl[t], base) + off
        n5 = int(5.0 / (STEP * 100))
        lb = longm[max(pc - n5, 0):pc].sum()
        sa = shortm[pc + 1:pc + 1 + n5].sum()
        tot = lb + sa
        imb = (sa - lb) / tot if tot > 0 else 0.0
        up = np.nonzero(shortm[pc + 1:pc + 1 + int(15 / (STEP * 100))] >= max(1e-9, 2 * np.median(shortm[shortm > 0]) if (shortm > 0).any() else 1e-9))[0]
        dn = np.nonzero(longm[max(pc - int(15 / (STEP * 100)), 0):pc][::-1] >= max(1e-9, 2 * np.median(longm[longm > 0]) if (longm > 0).any() else 1e-9))[0]
        rows.append((imb, (up[0] + 1) * STEP * 100 if len(up) else np.nan, (dn[0] + 1) * STEP * 100 if len(dn) else np.nan, lb, sa))
    df = pd.DataFrame(rows, index=idx, columns=["liq_imb", "liq_dist_up_pct", "liq_dist_dn_pct", "long_below_usd", "short_above_usd"])
    if return_last_map:
        return df, (longm, shortm, base, off)
    return df


def _bands_from_grid(longm, shortm, base, off, ref_price):
    pc = _gi(ref_price, base) + off
    n = int(BAND_PCT / (STEP * 100))
    bands = []
    nb = int(RANGE_PCT / BAND_PCT)
    for k in range(-nb, nb):
        lo_i, hi_i = pc + k * n + (1 if k >= 0 else 0), pc + (k + 1) * n + (1 if k >= 0 else 0)
        lo_i, hi_i = max(lo_i, 0), min(hi_i, len(longm))
        lo_pct, hi_pct = k * BAND_PCT, (k + 1) * BAND_PCT
        lv = float(longm[lo_i:hi_i].sum()) if k < 0 else 0.0
        sv = float(shortm[lo_i:hi_i].sum()) if k >= 0 else 0.0
        bands.append({"lo_pct": lo_pct, "hi_pct": hi_pct, "long_usd": round(lv, 0), "short_usd": round(sv, 0)})
    return bands


def summarize_bands(bands):
    lb = sum(b["long_usd"] for b in bands if b["hi_pct"] <= 0 and b["lo_pct"] >= -5)
    sa = sum(b["short_usd"] for b in bands if b["lo_pct"] >= 0 and b["hi_pct"] <= 5)
    tot = lb + sa
    allm = np.array([b["long_usd"] + b["short_usd"] for b in bands])
    nz = allm[allm > 0]
    thr = 2 * float(np.median(nz)) if len(nz) else 0.0
    up = [b for b in bands if b["short_usd"] > 0 and b["short_usd"] >= thr and b["lo_pct"] >= 0]
    dn = [b for b in reversed(bands) if b["long_usd"] > 0 and b["long_usd"] >= thr and b["hi_pct"] <= 0]
    top3 = float(np.sort(allm)[-3:].sum() / allm.sum()) if allm.sum() > 0 else 0.0
    return {"long_below_5pct_usd": round(lb), "short_above_5pct_usd": round(sa),
            "imbalance_short_minus_long": round((sa - lb) / tot, 3) if tot > 0 else 0.0,
            "nearest_dense_above_pct": up[0]["lo_pct"] if up else None,
            "nearest_dense_below_pct": dn[0]["hi_pct"] if dn else None,
            "top3_band_share": round(top3, 3), "total_mass_usd": round(float(allm.sum()))}


def _load_k5(symbol, asof):
    df = store.get_ohlcv(symbol, "5m")
    return df[df.index + pd.Timedelta("5min") <= asof]


def binance_proxy(coin="BTC", asof=None, days=28):
    asof = asof or dt.datetime.now(dt.timezone.utc)
    sym = coin + "USDT"
    con = _ro(deriv.DB)
    lo_ms = int((asof - dt.timedelta(days=days)).timestamp() * 1000)
    hi_ms = int(asof.timestamp() * 1000)
    # Binance hist timestamps may denote period start or end; assume START => known 5 min later (conservative, causal)
    oi = pd.read_sql_query("SELECT ts_ms, oi_value FROM oi_hist WHERE symbol=? AND ts_ms>=? AND ts_ms<=? ORDER BY ts_ms", con, params=(sym, lo_ms, hi_ms))
    ls = pd.read_sql_query("SELECT ts_ms, long_share FROM ls_ratio WHERE kind='global_acct' AND symbol=? AND ts_ms>=? AND ts_ms<=? ORDER BY ts_ms", con, params=(sym, lo_ms, hi_ms))
    con.close()
    if len(oi) < 300:
        return None
    to_idx = lambda s: pd.to_datetime(s, unit="ms", utc=True) + pd.Timedelta("5min")
    oi_s = pd.Series(oi["oi_value"].values, index=to_idx(oi["ts_ms"]))
    oi_s = oi_s[oi_s.index <= asof]
    ls_s = pd.Series(ls["long_share"].values, index=to_idx(ls["ts_ms"]))
    k5 = _load_k5(coin + "/USDT", asof)
    df, (lm, sm, base, off) = proxy_series(oi_s, ls_s, k5, return_last_map=True)
    ref = float(k5["close"].iloc[-1])
    bands = _bands_from_grid(lm, sm, base, off, ref)
    return {"source": "binance_proxy", "coin": coin, "asof": asof.strftime("%Y-%m-%dT%H:%M:%SZ"), "ref_price": ref, "bands": bands,
            "summary": summarize_bands(bands),
            "meta": {"kind": "ESTIMATE", "history_days": round((oi_s.index[-1] - oi_s.index[0]).total_seconds() / 86400, 1),
                     "verifiable": accumulated_days() >= MIN_DAYS_VALID,
                     "limits": "assumed leverage mix & proportional closes; positions older than the OI history are invisible"}}


def hl_map(coin="BTC", asof=None):
    asof = asof or dt.datetime.now(dt.timezone.utc)
    if not hl.DB.exists():
        return None
    con = _ro(hl.DB)
    a_iso = asof.strftime("%Y-%m-%dT%H:%M:%SZ")
    rows = hl.latest_positions(con, coin, a_iso)
    mk = con.execute("SELECT mid, open_interest FROM market WHERE coin=? AND snap_ts<=? ORDER BY snap_ts DESC LIMIT 1", (coin, a_iso)).fetchone()
    n_addr = con.execute("SELECT COUNT(*) FROM addrs").fetchone()[0]
    con.close()
    if not rows or not mk:
        return None
    ref = float(mk[0])
    nb = int(RANGE_PCT / BAND_PCT)
    long_b, short_b = np.zeros(nb), np.zeros(nb)
    tot_long = tot_short = 0.0
    for addr, szi, entry, liq, val, lev, ts in rows:
        if liq is None or liq <= 0:
            continue
        rel = (liq / ref - 1) * 100
        if szi > 0:
            tot_long += val
            if -RANGE_PCT <= rel < 0:
                long_b[int((rel + RANGE_PCT) // BAND_PCT)] += val
        else:
            tot_short += val
            if 0 <= rel < RANGE_PCT:
                short_b[int(rel // BAND_PCT)] += val
    bands = []
    for k in range(-nb, nb):
        lo_pct, hi_pct = k * BAND_PCT, (k + 1) * BAND_PCT
        bands.append({"lo_pct": lo_pct, "hi_pct": hi_pct, "long_usd": round(float(long_b[k + nb]) if k < 0 else 0.0),
                      "short_usd": round(float(short_b[k]) if k >= 0 else 0.0)})
    exch_oi = float(mk[1]) * ref
    return {"source": "hyperliquid_sample", "coin": coin, "asof": a_iso, "ref_price": ref, "bands": bands,
            "summary": dict(summarize_bands(bands), tracked_long_usd=round(tot_long), tracked_short_usd=round(tot_short)),
            "meta": {"kind": "MEASURED_SAMPLE", "positions": len(rows), "tracked_addresses": n_addr,
                     "coverage_of_exchange_oi_pct": round(100 * (tot_long + tot_short) / (2 * exch_oi), 2) if exch_oi else None,
                     "verifiable": False, "limits": "sample of addresses seen trading >= $25k via the public trades feed; no full account list exists"}}


def _vec(m, side):
    return np.array([b[side] for b in m["bands"]], float)


def compare(a, b):
    """Compare two maps (binance_proxy vs hyperliquid_sample) after normalising each side to shares of its own total."""
    if not a or not b:
        return {"available": False, "reason": "one of the maps is missing"}
    out = {"available": True}
    for side, name in (("long_usd", "below"), ("short_usd", "above")):
        x, y = _vec(a, side), _vec(b, side)
        xs, ys = x.sum(), y.sum()
        if xs <= 0 or ys <= 0:
            out["corr_" + name] = None
            continue
        x, y = x / xs, y / ys
        out["corr_" + name] = round(float(np.corrcoef(x, y)[0, 1]), 3) if x.std() > 0 and y.std() > 0 else None
        out["l1_distance_" + name] = round(float(np.abs(x - y).sum() / 2), 3)       # 0 identical .. 1 disjoint
    sa, sb = a["summary"], b["summary"]
    out["imbalance"] = {"binance_proxy": sa["imbalance_short_minus_long"], "hyperliquid": sb["imbalance_short_minus_long"],
                        "same_sign": (sa["imbalance_short_minus_long"] * sb["imbalance_short_minus_long"]) > 0}
    out["nearest_dense_above_pct"] = {"binance_proxy": sa["nearest_dense_above_pct"], "hyperliquid": sb["nearest_dense_above_pct"]}
    out["nearest_dense_below_pct"] = {"binance_proxy": sa["nearest_dense_below_pct"], "hyperliquid": sb["nearest_dense_below_pct"]}
    out["note"] = "binance_proxy is an exchange-wide ESTIMATE; hyperliquid is a MEASURED SAMPLE of a different venue - agreement is weak evidence, not validation"
    return out


def regime_features(asof=None, coin="BTC"):
    """Compact 'liq:' items for the regime agent (the two sources are kept separate)."""
    out = {}
    try:
        m = binance_proxy(coin, asof)
        if m:
            out["liq:binance_proxy_" + coin] = dict(m["summary"], ref_price=m["ref_price"], kind="ESTIMATE_unverified", history_days=m["meta"]["history_days"])
    except Exception as e:      # noqa: BLE001
        out["liq:binance_proxy_" + coin] = {"error": type(e).__name__}
    try:
        h = hl_map(coin, asof)
        if h:
            out["liq:hyperliquid_" + coin] = dict(h["summary"], kind="MEASURED_SAMPLE_unverified", positions=h["meta"]["positions"],
                                                   coverage_pct=h["meta"]["coverage_of_exchange_oi_pct"])
    except Exception as e:      # noqa: BLE001
        out["liq:hyperliquid_" + coin] = {"error": type(e).__name__}
    return out
