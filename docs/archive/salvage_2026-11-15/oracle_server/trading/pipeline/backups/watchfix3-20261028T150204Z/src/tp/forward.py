"""Forward PAPER tracker for the pre-registered candidates (no orders, no exchange keys; read-only klines + regime log).

Each candidate is a deterministic function of data up to each bar, so its forward track record = the same function evaluated on bars
AFTER its registration timestamp (runs/forward_registry.json, created once, never changed). Evaluation starts flat at registration,
charges the primary futures cost model and real funding. Success / failure criteria are fixed in research/FORWARD_CANDIDATES.md.
C6 applies the scheduler's recorded risk_multiplier (<= 1) to candidate C3; the only place the agent's judgement is evaluated, forward only."""
import datetime as dt
import json

import numpy as np
import pandas as pd

from . import costs, futbt, metrics, pool, research
from .config import RUNS, scrub

REG = RUNS / "forward_registry.json"
BASE = costs.BASE_FUT
C3 = "C3_trend_mtf_ls_BTC_1h"
CANDIDATES = {
    "C0_buyhold_BTC": {"desc": "benchmark: BTC perp long 1x", "kind": "bh", "sym": "BTC/USDT", "tf": "1h"},
    "C0_buyhold_ETH": {"desc": "benchmark: ETH perp long 1x", "kind": "bh", "sym": "ETH/USDT", "tf": "1h"},
    "C1_trend_mtf_long_ETH_1h": {"desc": "trend_mtf long ETH 1h", "kind": "single", "st": "coin_trend_mtf", "side": "long", "sym": "ETH/USDT", "tf": "1h"},
    "C2_btc_alt_long_ETH_4h": {"desc": "btc_regime_alt long ETH 4h", "kind": "single", "st": "coin_btc_regime_alt", "side": "long", "sym": "ETH/USDT", "tf": "4h"},
    C3: {"desc": "trend_mtf long/short BTC 1h (base for overlays)", "kind": "single", "st": "coin_trend_mtf", "side": "ls", "sym": "BTC/USDT", "tf": "1h"},
    "C3v_voltarget": {"desc": "C3 x deterministic vol target", "kind": "overlay", "base": C3, "overlay": "vol"},
    "C3f_fomc": {"desc": "C3 flat +-6h around FOMC statements", "kind": "overlay", "base": C3, "overlay": "fomc"},
    "C3r_retire": {"desc": "C3 with 30d shadow-Sharpe retirement", "kind": "overlay", "base": C3, "overlay": "retire"},
    "C4_A1_rule_BTC": {"desc": "A1 regime rule table (deterministic classifier) BTC, 15m clock", "kind": "a1", "sym": "BTC/USDT", "tf": "15m"},
    "C6_llm_rm_on_C3": {"desc": "C3 x scheduler risk_multiplier (LLM regime agent, forward only)", "kind": "overlay", "base": C3, "overlay": "llm"},
}
CRITERIA = {"min_days": 28, "min_trades": 20, "success_sharpe": 0.5, "success_mdd": 0.15, "fail_mdd": 0.20, "fail_after_days": 28}


def now_utc():
    return dt.datetime.now(dt.timezone.utc)


def registry(now=None):
    """Create-once registry: candidate -> registration timestamp. Existing entries are never modified."""
    cur = json.loads(REG.read_text()) if REG.exists() else {}
    changed = False
    for k in CANDIDATES:
        if k not in cur:
            cur[k] = (now or now_utc()).strftime("%Y-%m-%dT%H:%M:%SZ")
            changed = True
    if changed:
        REG.write_text(json.dumps(cur, indent=1, sort_keys=True))
    return cur


def llm_rm_series(index, tf):
    """risk_multiplier (<=1) of the latest crypto regime-log row logged at or before each bar close (llm and carried rows)."""
    from . import regime
    con = regime.log_con()
    rows = con.execute("SELECT logged_at, output_json FROM regime_log WHERE market='crypto' ORDER BY id").fetchall()
    con.close()
    if not rows:
        return np.ones(len(index))
    t = np.array([int(pd.Timestamp(r[0], tz="UTC").timestamp() * 1000) if pd.Timestamp(r[0]).tzinfo is None
                  else int(pd.Timestamp(r[0]).timestamp() * 1000) for r in rows])
    v = np.array([min(1.0, float(json.loads(r[1])["risk_multiplier"])) for r in rows])
    q = research.ms(index) + research.TF_MS[tf]
    pos = np.searchsorted(t, q, side="right") - 1
    return np.where(pos >= 0, v[np.clip(pos, 0, len(v) - 1)], 1.0)


_SIG_FP = {}     # (strategy, side, sym, tf) -> fingerprint of the input frame(s) the memoised signal was computed from


def _fp(df):
    return (len(df), df.index[-1].value if len(df) else None)


def _signal(st, side, sym, tf, d):
    """Signal on exactly d's index. research.get_signal memoises per (strategy, side, sym, tf) for the life of the process, but the kline
    store grows while tp-watch runs (tp-news appends bars every 30 min), so a cached Series can have a different length than the freshly
    loaded frame (-> 'operands could not be broadcast together'). The cache entry is only reused if the fingerprint (length + last bar time) of
    d - and of the BTC context frame for NEEDS_BTC strategies - is unchanged; otherwise it is dropped and recomputed on d. If the BTC context
    ends before d (research.with_btc would silently give a flat 0 tail) the signal is refused instead of cached."""
    key = (st, side, sym, tf)
    fp = (_fp(d),)
    if getattr(pool.load(st), "NEEDS_BTC", False):
        b = research.load_df("BTC/USDT", tf)
        if len(b) == 0 or (len(d) and b.index[-1] < d.index[-1]):
            research._SIG_CACHE.pop(key, None)
            _SIG_FP.pop(key, None)
            raise ValueError("BTC context for %s/%s ends %s, before the last %s bar %s: signal withheld" % (
                st, tf, b.index[-1] if len(b) else None, sym, d.index[-1] if len(d) else None))
        fp += (_fp(b),)
    cached = research._SIG_CACHE.get(key)
    if cached is not None and (_SIG_FP.get(key) != fp or not cached.index.equals(d.index)):
        research._SIG_CACHE.pop(key, None)
    s = research.get_signal(st, side, sym, tf, d)
    if len(s) != len(d) or not s.index.equals(d.index):
        research._SIG_CACHE.pop(key, None)
        raise ValueError("signal %s/%s/%s/%s index mismatch: %d vs %d bars" % (st, side, sym, tf, len(s), len(d)))
    _SIG_FP[key] = fp
    return s


def candidate_signal(name):
    c = CANDIDATES[name]
    k = c["kind"]
    if k == "bh":
        d = research.load_df(c["sym"], c["tf"])
        return d, pd.Series(1.0, index=d.index), c["sym"], c["tf"]
    if k == "single":
        d = research.load_df(c["sym"], c["tf"])
        return d, _signal(c["st"], c["side"], c["sym"], c["tf"], d), c["sym"], c["tf"]
    if k == "a1":
        clock = c["tf"]
        d = research.load_df(c["sym"], clock)
        frames, cfg = {clock: d}, {}                    # each timeframe frame is loaded once per call (one consistent snapshot)
        for st, side, tf, _w in research.A1_TABLE.values():
            if tf not in frames:
                frames[tf] = research.load_df(c["sym"], tf)
            cfg[(st, side, tf)] = research.align(_signal(st, side, c["sym"], tf, frames[tf]), tf, d.index, clock)
        labs = research.regime_codes("BTC/USDT", d, clock)
        return d, pd.Series(research.a1_signal(labs, cfg), index=d.index), c["sym"], clock
    d, sig, sym, tf = candidate_signal(c["base"])
    fr = research.fund_arr(sym, d, tf)
    if c["overlay"] == "vol":
        sig = sig * research.vol_scale(d, tf)
    elif c["overlay"] == "fomc":
        from . import fomc
        sig = sig.where(~research.fomc_mask(d, tf, fomc.statement_times()), 0.0)
    elif c["overlay"] == "retire":
        sig = sig * research.retire_active(d, tf, sig.values, fr)
    elif c["overlay"] == "llm":
        sig = sig * llm_rm_series(d.index, tf)
    return d, sig, sym, tf


def judge(kind, days, trades, sr, mdd, total_return):
    C = CRITERIA
    if kind == "bh":
        return "BENCHMARK"
    if mdd > C["fail_mdd"] and days >= 7:
        return "FAIL (mdd)"
    if days < C["min_days"] or trades < C["min_trades"]:
        return "RUNNING"
    if sr >= C["success_sharpe"] and mdd <= C["success_mdd"] and total_return > 0:
        return "SUCCESS"
    if days >= C["fail_after_days"] and sr < 0:
        return "FAIL (sharpe<0)"
    return "INCONCLUSIVE"


def evaluate(name, reg, with_r=False):
    d, sig, sym, tf = candidate_signal(name)
    t0 = pd.Timestamp(reg[name])
    t0 = t0.tz_convert("UTC") if t0.tzinfo else t0.tz_localize("UTC")
    i0 = int(np.searchsorted(d.index, t0))          # first bar OPENING at/after registration; starts flat
    dd, ss = d.iloc[i0:], sig.iloc[i0:]
    if len(dd) < 5:
        return {"candidate": name, "status": "RUNNING", "days": 0.0, "note": "no bars after registration yet"}
    fr = research.fund_arr(sym, d, tf)[i0:]
    res = futbt.simulate(dd, ss, BASE, 1.0, 1.0, fr)
    r = res["ret"].values
    days = len(dd) * research.TF_MS[tf] / 86400_000
    mdd = metrics.max_drawdown(r)
    sr = metrics.sharpe_annual(r, research.PPY[tf])
    tot = float(res["equity"].iloc[-1] - 1)
    out = {"candidate": name, "desc": CANDIDATES[name]["desc"], "days": round(days, 1), "bars": len(dd), "trades": int(res["n_open"]),
            "total_return": round(tot, 4), "sharpe": round(float(sr), 2), "mdd": round(float(mdd), 4),
            "fees_pct": round(100 * res["fees"], 3), "funding_pct": round(100 * res["funding"], 3), "liquidations": res["n_liq"],
            "status": judge(CANDIDATES[name]["kind"], days, int(res["n_open"]), sr, mdd, tot)}
    if with_r:
        out["_r"] = r                      # never serialised: callers that need the series (budget policy) ask for it explicitly
    return out


def evaluate_all(now=None):
    reg = registry(now)
    out = []
    for k in CANDIDATES:
        try:
            out.append(evaluate(k, reg))
        except Exception as e:      # noqa: BLE001  one candidate failing must not hide the others
            out.append({"candidate": k, "status": "ERROR", "note": scrub("%s: %s" % (type(e).__name__, e), 200)})
    return out


def summary_line(rows=None):
    rows = evaluate_all() if rows is None else rows
    cnt = {}
    for r in rows:
        s = r["status"].split(" ")[0]
        cnt[s] = cnt.get(s, 0) + 1
    days = max([r.get("days", 0) for r in rows] + [0])
    return "forward paper %.0f일차: " % days + " ".join("%s %d" % kv for kv in sorted(cnt.items()))
