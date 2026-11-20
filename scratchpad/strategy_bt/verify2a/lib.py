"""Shared helpers for verify2a (Group A). Runs the real plugin signals through common.engine.simulate
(imported read-only); delay/slippage/fee are applied through the wrapper only."""
import sys, json, glob, csv, importlib.util
from pathlib import Path
import numpy as np, pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
from common.engine import simulate  # noqa: E402  (read-only use)

DATA = ROOT.parent / "bb_stoch_stc" / "data"
SYMS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT"]
CAPITAL, NOTIONAL = 10000.0, 1000.0
CANDS = ["jesse_simple_bollinger", "btc-max10-nyse-close", "btc-macd-15-41-12",
         "turtle-system-2", "btc-bollinger-37-16", "btc-roc-36-9pct"]
SIGCOLS = ["long_entry", "short_entry", "long_exit", "short_exit"]


def load_summary():
    rows = []
    for p in sorted(glob.glob(str(ROOT / "results" / "slice_*" / "summary.csv"))):
        with open(p, newline="", encoding="utf-8") as f:
            rows += list(csv.DictReader(f))
    return rows


def find_plugin(sid):
    hits = glob.glob(str(ROOT / "plugins" / "slice_*" / f"{sid}.py"))
    if not hits:
        raise FileNotFoundError(sid)
    return hits[0]


_cache = {}
def load_plugin(path):
    if path not in _cache:
        spec = importlib.util.spec_from_file_location("sp_" + Path(path).stem.replace("-", "_"), path)
        mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); _cache[path] = mod
    return _cache[path]


def test_frames(tf, syms=SYMS):
    """TEST slice exactly as common.protocol.evaluate builds it (last 40% of each symbol's file)."""
    out = {}
    for s in syms:
        p = DATA / f"{s}_{tf}.parquet"
        if not p.exists():
            continue
        d = pd.read_parquet(p); cut = int(len(d) * .6)
        ts = d.index[cut:]
        out[s] = (d.iloc[cut:].reset_index(drop=True), ts)
    return out


def delay_signals(sig, k):
    """Shift every signal column k bars later (extra execution delay)."""
    if k <= 0:
        return sig
    s = sig.copy()
    for c in s.columns:
        if c in SIGCOLS:
            s[c] = s[c].astype(bool).shift(k, fill_value=False)
        else:
            s[c] = s[c].shift(k)
    return s


def run_row(sid, tf, params, delay=0, slippage=0.0002, fee=0.0004, frames=None, plugin_path=None):
    """Return {symbol: (trades, df, ts, side)} for the TEST window."""
    plugin = load_plugin(plugin_path or find_plugin(sid))
    side = getattr(plugin, "SIDES", "both")
    frames = frames or test_frames(tf)
    out = {}
    for s, (df, ts) in frames.items():
        sig = plugin.signals(df.copy(), **params)
        sig = delay_signals(sig, delay)
        trades, _ = simulate(df, sig, params, side=side, fee=fee, slippage=slippage)
        out[s] = (trades, df, ts)
    return out, side


def total_pct(res):
    return float(sum(t["pct"] for tr, _, _ in res.values() for t in tr))


def candidate_row(sid, rows=None):
    rows = rows or load_summary()
    r = [x for x in rows if x["strategy_id"] == sid and x["status"] == "DONE"]
    assert len(r) == 1, (sid, len(r))
    r = r[0]
    return r["timeframe"], json.loads(r["params"]), r
