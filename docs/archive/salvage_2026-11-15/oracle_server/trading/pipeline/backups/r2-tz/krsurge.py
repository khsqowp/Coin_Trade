"""KR surge-chase PAPER FORWARD SIMULATOR on 1-minute bars. There is NO order, broker or KIS-order code in this module.

Why not daily bars: the strategy exits at +5% / -3% intraday; from OHLC alone the order in which a day's high and low occurred is
unknowable, so any daily backtest would be fiction. It can only be evaluated on stored minute data (data/intraday/kr, collected by
tp.kisintra) and, until MIN_SESSIONS sessions exist, every result here is labelled "unverifiable" (the pool module
`kr_surge_chase.verifiable()` keeps the gate closed).

Conservative, parameterised assumptions (all in PARAMS):
  * limit-up proximity: when the day's change >= limit_up_block_pct the stock is treated as NOT buyable (queue/remainder problem).
  * entry fills at the NEXT minute's open + entry_slip_pct (we are chasing).
  * stop-loss fills at the stop level minus stop_slip_pct (stops in fast markets slip; if the minute opens below the stop, the open
    minus slippage is used); a minute that touches both TP and SL counts as STOP first.
  * costs: buy 0.015% commission; sell 0.015% commission + 0.18% transaction tax (conservative round numbers; verify with the broker).
  * forced flat at eod_flat (15:20, before the closing auction) at that bar's close minus slippage.
"""
import datetime as dt
import json

import pandas as pd

from .config import DATA

KST = dt.timezone(dt.timedelta(hours=9))
PARAMS = {"min_day_chg_pct": 6.0, "vol_mult": 3.0, "limit_up_block_pct": 28.0, "take_profit_pct": 5.0, "stop_loss_pct": -3.0,
          "entry_slip_pct": 0.15, "stop_slip_pct": 0.5, "eod_slip_pct": 0.2, "buy_cost_pct": 0.015, "sell_cost_pct": 0.195,
          "eod_flat": "15:20", "first_entry": "09:05", "last_entry": "14:30", "max_entries_per_symbol_day": 1}
MIN_SESSIONS = 60


def simulate_day(bars, prev_close, params=None):
    """bars: 1-min OHLCV (UTC or KST tz-aware index, one session). Returns list of trade dicts (net of costs)."""
    p = dict(PARAMS, **(params or {}))
    b = bars.copy()
    b.index = b.index.tz_convert(KST)
    b = b.sort_index()
    hhmm = lambda s: dt.datetime.strptime(s, "%H:%M").time()
    trades, entries, n = [], 0, len(b)
    skipped_limit = 0
    o, h, l, c, v = (b[k].values for k in ("open", "high", "low", "close", "volume"))
    t_first, t_last, t_eod = hhmm(p["first_entry"]), hhmm(p["last_entry"]), hhmm(p["eod_flat"])
    i = 0
    while i < n - 1:
        tm = b.index[i].time()
        if tm < t_first or tm > t_last or entries >= p["max_entries_per_symbol_day"]:
            i += 1
            continue
        chg = (c[i] / prev_close - 1) * 100
        if chg >= p["min_day_chg_pct"]:
            if chg >= p["limit_up_block_pct"]:
                skipped_limit += 1
                i += 1
                continue
            win = v[max(0, i - 4):i + 1].sum()
            avg5 = v[:i - 4].mean() * 5 if i >= 10 else 0           # baseline = minutes BEFORE the 5-minute window
            if avg5 > 0 and win >= p["vol_mult"] * avg5:
                px = o[i + 1] * (1 + p["entry_slip_pct"] / 100)
                if (px / prev_close - 1) * 100 >= p["limit_up_block_pct"]:
                    skipped_limit += 1
                    i += 1
                    continue
                entries += 1
                tp, sl = px * (1 + p["take_profit_pct"] / 100), px * (1 + p["stop_loss_pct"] / 100)
                exit_px, reason, j = None, None, i + 1
                while j < n:
                    if b.index[j].time() >= t_eod:
                        exit_px, reason = c[j] * (1 - p["eod_slip_pct"] / 100), "eod_flat"
                        break
                    if o[j] <= sl:
                        exit_px, reason = o[j] * (1 - p["stop_slip_pct"] / 100), "stop_gap"
                        break
                    if l[j] <= sl:                       # stop first when both are touched in the same minute
                        exit_px, reason = sl * (1 - p["stop_slip_pct"] / 100), "stop_loss"
                        break
                    if h[j] >= tp:
                        exit_px, reason = tp, "take_profit"
                        break
                    j += 1
                if exit_px is None:
                    exit_px, reason, j = c[n - 1] * (1 - p["eod_slip_pct"] / 100), "eod_flat", n - 1
                net = (exit_px / px - 1) * 100 - p["buy_cost_pct"] - p["sell_cost_pct"]
                trades.append({"entry_time": str(b.index[i + 1]), "exit_time": str(b.index[min(j, n - 1)]), "entry": round(px, 2),
                               "exit": round(exit_px, 2), "reason": reason, "net_pct": round(net, 3), "day_chg_at_signal_pct": round(chg, 2)})
                i = j
                continue
        i += 1
    if skipped_limit and not trades:
        trades.append({"skipped_limit_up": skipped_limit, "net_pct": None})
    return [t for t in trades if t.get("net_pct") is not None]


def sessions_available():
    root = DATA / "intraday" / "kr"
    return sorted(p.name for p in root.glob("2*") if p.is_dir()) if root.exists() else []


def prev_closes(day):
    """prdy_close per code from the polling snapshots of that day (first snapshot wins)."""
    f = DATA / "intraday" / "kr" / ("snapshots_%s.jsonl" % day)
    out = {}
    if f.exists():
        for line in f.read_text().splitlines():
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if r.get("prdy_close"):
                out.setdefault(r["code"], r["prdy_close"])
    return out


def forward_sim(params=None):
    days = sessions_available()
    allt = []
    for d in days:
        pc = prev_closes(d)
        for f in (DATA / "intraday" / "kr" / d).glob("*.parquet"):
            if f.stem not in pc:
                continue
            for t in simulate_day(pd.read_parquet(f), pc[f.stem], params):
                allt.append(dict(t, day=d, code=f.stem))
    n = len(allt)
    rets = [t["net_pct"] for t in allt]
    return {"sessions": len(days), "sessions_required": MIN_SESSIONS, "trades": n,
            "win_rate": round(sum(r > 0 for r in rets) / n, 3) if n else None,
            "avg_net_pct": round(sum(rets) / n, 3) if n else None,
            "status": "UNVERIFIABLE (forward paper only)" if len(days) < MIN_SESSIONS else "forward-evidence (still owner review required)",
            "params": dict(PARAMS, **(params or {})), "orders_placed": 0}
