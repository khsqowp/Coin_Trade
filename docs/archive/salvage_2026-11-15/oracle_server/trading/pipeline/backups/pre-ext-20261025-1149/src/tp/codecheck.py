"""Deterministic checks for benchmark code generation (run inside the no-network sandbox)."""
import numpy as np
import pandas as pd

from . import bt


def ref_sma(df):
    c = df["close"]
    s = c.rolling(10).mean() > c.rolling(30).mean()
    return s.astype(float)


def ref_rsi(df):
    d = df["close"].diff()
    g = d.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    l = (-d.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
    rsi = 100 - 100 / (1 + g / l)
    out, state = [], 0.0
    for v in rsi.values:
        if not np.isnan(v):
            if v < 30:
                state = 1.0
            elif v > 55:
                state = 0.0
        out.append(state)
    return pd.Series(out, index=df.index)


REFS = {"sma": ref_sma, "rsi": ref_rsi}


def run_checks(path, spec, df):
    res = {}
    try:
        fn = bt.load_signal_fn(path)
    except Exception as e:
        return {"load": False, "error": "%s: %s" % (type(e).__name__, str(e)[:150]),
                "t1_valid_output": False, "t2_no_lookahead": False, "t3_matches_reference": False,
                "t4_pure_deterministic": False, "t5_short_input": False}
    res["load"] = True
    # T1 valid output
    try:
        s = fn(df.copy())
        ok = isinstance(s, pd.Series) and s.index.equals(df.index) and not s.isna().any() \
            and bool(s.isin([0, 1]).all())
        res["t1_valid_output"] = bool(ok)
    except Exception as e:
        s = None
        res["t1_valid_output"] = False
        res["error"] = "%s: %s" % (type(e).__name__, str(e)[:150])
    # T2 no lookahead
    try:
        res["t2_no_lookahead"] = bool(bt.lookahead_check(fn, df, n_probes=12)["passed"])
    except Exception:
        res["t2_no_lookahead"] = False
    # T3 agrees with reference after warm-up
    try:
        ref = REFS[spec](df)
        res["t3_matches_reference"] = bool((s.iloc[200:] == ref.iloc[200:]).mean() >= 0.97)
    except Exception:
        res["t3_matches_reference"] = False
    # T4 deterministic, does not mutate input
    try:
        d1 = df.copy()
        a = fn(d1)
        b = fn(df.copy())
        res["t4_pure_deterministic"] = bool(d1.equals(df) and a.equals(b))
    except Exception:
        res["t4_pure_deterministic"] = False
    # T5 short input
    try:
        short = df.iloc[:20].copy()
        r = fn(short)
        res["t5_short_input"] = bool(len(r) == 20 and not r.isna().any())
    except Exception:
        res["t5_short_input"] = False
    return res
