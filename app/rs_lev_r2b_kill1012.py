"""R2-B step 7: 2026-10-12 05:50 false-kill forensics: numbers + counterfactual (hold the 16 killed positions until the next scheduled rebalance 10-14 09:14).
Read-only: state copy + public 1m mark klines saved by rs_lev_r2b_fetch_live.py. usage: python rs_lev_r2b_kill1012.py <state.json> <live_dir>"""
import json, os, re, sys
import numpy as np, pandas as pd
s = json.load(open(sys.argv[1])); live = sys.argv[2]
T0 = int(pd.Timestamp("2026-09-24", tz="UTC").timestamp() * 1000)
ms = lambda ts: pd.Timestamp(ts).value // 10**6
eh = s["equity_history"]
def at(prefix): return [x for x in eh if x["ts"].startswith(prefix)]
b = [x for x in eh if "2026-10-12T05:30" <= x["ts"] <= "2026-10-12T05:48"][-1]; a = [x for x in eh if x["ts"] >= "2026-10-12T05:50:11"][0]
hw_b = b["equity_usdt"] / (1 - b["drawdown"]); hw_a = a["equity_usdt"] / (1 - a["drawdown"])
print(f"BEFORE {b['ts'][:19]}: equity {b['equity_usdt']:.3f} dd {b['drawdown']:.4f} implied hwm {hw_b:.2f} total_pnl {b['total_pnl_usdt']:.2f} implied inception {b['equity_usdt']-b['total_pnl_usdt']:.2f}")
print(f"AFTER  {a['ts'][:19]}: equity {a['equity_usdt']:.3f} dd {a['drawdown']:.4f} implied hwm {hw_a:.2f} total_pnl {a['total_pnl_usdt']:.2f} implied inception {a['equity_usdt']-a['total_pnl_usdt']:.2f}")
print(f"hwm shift {hw_a-hw_b:.2f}; inception shift {(a['equity_usdt']-a['total_pnl_usdt'])-(b['equity_usdt']-b['total_pnl_usdt']):.2f}; equity change across event {a['equity_usdt']-b['equity_usdt']:+.3f} USDT")
print(f"CORRECT dd at kill = 1 - {a['equity_usdt']:.3f}/{hw_b:.2f} = {1-a['equity_usdt']/hw_b:.4f} (threshold 0.35); mistaken dd = {a['drawdown']:.4f}")
# max true dd since the old hwm during 10-12 to see margin to kill
pre = [x for x in eh if "2026-10-05" <= x["ts"] <= "2026-10-12T05:50"]
hw = max(x["equity_usdt"] for x in pre)
print(f"raw max equity 10-05..10-12 05:50 = {hw:.2f}; min equity since = {min(x['equity_usdt'] for x in pre if x['ts']>='2026-10-12'):.2f}")
# counterfactual
pos = {}
for e in s["trade_log"]:
    m = re.match(r"\[KILL\] (\w+) (long|short) ([\d.]+) 청산", e["message"])
    if m and e["ts"].startswith("2026-10-12T05:50"): pos[m.group(1)] = (1 if m.group(2) == "long" else -1) * float(m.group(3))
def px(x, t):
    a_ = np.load(os.path.join(live, f"mark1m_{x}.npy")); m_ = (t - T0) // 60000; fr = ((t - T0) % 60000) / 60000
    return a_[m_, 0] + (a_[m_, 3] - a_[m_, 0]) * fr
t1 = ms("2026-10-12T05:50:11.100Z"); t2 = ms("2026-10-14T09:14:27.632Z")
pnl = sum(q * (px(x, t2) - px(x, t1)) for x, q in pos.items())
gross = sum(abs(q) * px(x, t1) for x, q in pos.items())
print(f"killed positions {len(pos)}, gross {gross:.1f} USDT ({gross/a['equity_usdt']:.2f}x equity)")
print(f"counterfactual hold-through PnL {pnl:+.2f} USDT ({pnl/a['equity_usdt']:+.2%} of equity) from kill to 10-14 09:14 (excl. fees/funding; kill closing fee/slippage unmodelled)")
ts = np.arange(t1 - t1 % 60000, t2, 60000)
path = np.zeros(len(ts))
for x, q in pos.items():
    arr = np.load(os.path.join(live, f"mark1m_{x}.npy")); path += q * (arr[((ts - T0) // 60000).astype(int), 3] - px(x, t1))
print(f"counterfactual path: min {path.min():+.2f} ({path.min()/a['equity_usdt']:+.2%}), max {path.max():+.2f} ({path.max()/a['equity_usdt']:+.2%}) vs equity {a['equity_usdt']:.1f}")
