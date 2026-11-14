"""Trusted backtest engine (long/flat). Strategies only produce signals; the engine owns execution.

Execution model: a signal computed from bars <= t is executed at the OPEN of bar t+1.
Costs: fee + slippage charged on every position change at that open (per side).
"""
import importlib.util
import math

import numpy as np
import pandas as pd

FEE = 0.001      # 0.10% per side (Binance spot taker, conservative)
SLIP = 0.0005    # 5 bps per side
# market -> (fee per side, slippage per side, periods per year). KR equities: commission ~0.015% + sales tax
# ~0.18% on sells, approximated conservatively as 0.11% per side. KR is analysis-only (no orders anywhere).
COSTS = {"crypto": (FEE, SLIP, 365), "kr": (0.0011, 0.0005, 252)}


def load_signal_fn(path):
    spec = importlib.util.spec_from_file_location("candidate_strategy", str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.generate_signals


def clean_signals(sig, index):
    if not isinstance(sig, pd.Series):
        raise TypeError("generate_signals must return a pandas Series")
    if not sig.index.equals(index):
        raise ValueError("signal index must equal input index")
    bad = int((~sig.dropna().isin([0, 1])).sum())
    return sig.fillna(0.0).clip(0.0, 1.0).astype(float), bad


def simulate(df, sig, fee=FEE, slip=SLIP):
    """Returns per-bar strategy returns and held position (h_t = sig_{t-1})."""
    h = sig.shift(1).fillna(0.0)
    h_prev = h.shift(1).fillna(0.0)
    gap = df["open"] / df["close"].shift(1) - 1.0
    intra = df["close"] / df["open"] - 1.0
    gap.iloc[0] = 0.0
    ret = h_prev * gap + h * intra - (h - h_prev).abs() * (fee + slip)
    return ret, h


def _stats(ret, h, ppy):
    n = len(ret)
    if n < 2:
        return {"bars": n, "trades": 0, "sharpe": 0.0, "mdd": 0.0, "total_return": 0.0,
                "win_rate": None, "exposure": 0.0, "avg_trade_ret": None}
    eq = (1 + ret).cumprod()
    mdd = float((1 - eq / eq.cummax()).max())
    sd = ret.std(ddof=1)
    sharpe = float(ret.mean() / sd * math.sqrt(ppy)) if sd and sd > 0 else 0.0
    entries = (h > 0) & (h.shift(1).fillna(0.0) == 0)
    entries.iloc[0] = bool(h.iloc[0] > 0)
    seg = entries.cumsum().where(h > 0)
    trade_rets = (1 + ret).groupby(seg).prod() - 1 if seg.notna().any() else pd.Series(dtype=float)
    return {
        "bars": n, "trades": int(entries.sum()), "sharpe": round(sharpe, 4), "mdd": round(mdd, 4),
        "total_return": round(float(eq.iloc[-1] - 1), 4),
        "win_rate": round(float((trade_rets > 0).mean()), 4) if len(trade_rets) else None,
        "avg_trade_ret": round(float(trade_rets.mean()), 5) if len(trade_rets) else None,
        "exposure": round(float((h > 0).mean()), 4),
    }


def lookahead_check(signal_fn, df, n_probes=40, seed=0):
    """Truncation test: the signal at bar k must not change when bars > k are removed."""
    full, _ = clean_signals(signal_fn(df.copy()), df.index)
    n = len(df)
    lo = min(220, n // 2)
    rng = np.random.RandomState(seed)
    ks = sorted(set(rng.randint(lo, n - 1, size=n_probes).tolist() + [n - 2]))
    mism, errors = [], 0
    for k in ks:
        try:
            part = df.iloc[:k + 1].copy()
            s = signal_fn(part)
            s = s.reindex(part.index).fillna(0.0).clip(0, 1)
            tail = 5  # compare the last few bars of the truncated run with the full run
            if (s.iloc[-tail:].values - full.iloc[k + 1 - tail:k + 1].values).__abs__().max() > 1e-9:
                mism.append(int(k))
        except Exception:
            errors += 1
    return {"probes": len(ks), "mismatches": len(mism), "errors": errors, "mismatch_bars": mism[:10],
            "passed": len(mism) == 0 and errors == 0}


def evaluate(df, signal_fn, ppy, split=0.6, folds=4, fee=FEE, slip=SLIP):
    sig, bad = clean_signals(signal_fn(df.copy()), df.index)
    ret, h = simulate(df, sig, fee, slip)
    cut = int(len(df) * split)
    bh_ret = df["close"].pct_change().fillna(0.0)
    bh_h = pd.Series(1.0, index=df.index)
    fsize = len(df) // folds
    fold_stats = [_stats(ret.iloc[i * fsize:(i + 1) * fsize], h.iloc[i * fsize:(i + 1) * fsize], ppy)
                  for i in range(folds)]
    return {
        "params": {"fee": fee, "slippage": slip, "execution": "next_bar_open", "split": split,
                   "periods_per_year": ppy, "bars": len(df),
                   "first": df.index[0].isoformat(), "last": df.index[-1].isoformat()},
        "invalid_signal_values": bad,
        "full": _stats(ret, h, ppy),
        "in_sample": _stats(ret.iloc[:cut], h.iloc[:cut], ppy),
        "out_of_sample": _stats(ret.iloc[cut:], h.iloc[cut:], ppy),
        "folds": fold_stats,
        "buy_and_hold": _stats(bh_ret, bh_h, ppy),
        "lookahead_check": lookahead_check(signal_fn, df),
    }
