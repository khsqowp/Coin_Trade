"""Deterministic synthetic stress frames for PROTECTIVE rules (stop-loss style rules that may never fire in history).

Policy (owner decision): a rule marked `protective` is NOT blocked as dead merely because it never changes the historical
signals. Instead it must demonstrably fire on injected stress paths:
  gap_crash      - a one-bar gap down (-12%, -25%) after which prices stay low
  consecutive    - 10 consecutive -3% bars
  halt_gap       - a trading-halt-like flat/zero-volume stretch followed by a -20% reopening gap
Each scenario is injected at bars where the FULL strategy is long (so there is a position to protect).
A rule "fires" in a scenario if (a) switching it off lets the strategy stay long where the full strategy is flat
(plain test), or (b) the same holds with all OTHER exit/protective rules switched off (isolated test: shows the guard
works on its own even if another exit usually triggers first - the `hard_catastrophe_stop` case). If neither ever
happens in any scenario the rule is truly dead and BLOCKS.  No randomness, no network, no LLM.
"""
import numpy as np
import pandas as pd

WINDOW_BEFORE = 12000       # warm-up bars kept before the injection point (long HTF indicators)
AFTER = 40
POINTS = 3                  # injection points per scenario type
MIN_HELD = 3                # position must already be held this many bars


def _shift_after(df, t, factor):
    out = df.copy()
    cols = ["open", "high", "low", "close"]
    out.iloc[t + 1:, [out.columns.get_loc(c) for c in cols]] = out.iloc[t + 1:][cols].values * factor
    return out


def inject(df, t, kind):
    """df: frame; t: integer position of the last unmodified bar. Returns a new frame ending AFTER bars later."""
    d = df.iloc[max(0, t - WINDOW_BEFORE):t + 1 + AFTER].copy()
    t = min(t, WINDOW_BEFORE)
    ix = {c: d.columns.get_loc(c) for c in ("open", "high", "low", "close", "volume")}
    if kind.startswith("gap_"):
        g = float(kind.split("_")[1]) / 100.0
        d = _shift_after(d, t, 1.0 - g)
    elif kind == "consecutive":
        c0 = float(d["close"].iloc[t])
        scale_after = 0.97 ** 10
        later = d.iloc[t + 11:][["open", "high", "low", "close"]].values * (c0 * scale_after / float(d["close"].iloc[t + 10]))
        d.iloc[t + 11:, [ix["open"], ix["high"], ix["low"], ix["close"]]] = later
        prev = c0
        for k in range(1, 11):
            c = c0 * 0.97 ** k
            d.iloc[t + k, [ix["open"], ix["high"], ix["low"], ix["close"]]] = [prev, prev, c, c]
            prev = c
    elif kind == "halt_gap":
        c0 = float(d["close"].iloc[t])
        d = _shift_after(d, t + 3, 0.80)
        for k in (1, 2, 3):
            d.iloc[t + k, [ix["open"], ix["high"], ix["low"], ix["close"], ix["volume"]]] = [c0, c0, c0, c0, 0.0]
    else:
        raise ValueError(kind)
    return d, t


SCENARIOS = ("gap_12", "gap_25", "consecutive", "halt_gap")


def held_points(sig, n=POINTS):
    """Evenly spaced bars where the strategy has been long for >= MIN_HELD bars and at least AFTER bars remain."""
    s = sig.values
    run = np.zeros(len(s), dtype=int)
    for i in range(1, len(s)):
        run[i] = run[i - 1] + 1 if s[i] > 0 and s[i - 1] > 0 else 0
    ok = [i for i in range(len(s) - AFTER - 1) if run[i] >= MIN_HELD]
    if not ok:
        return []
    idx = np.linspace(0, len(ok) - 1, num=min(n, len(ok))).round().astype(int)
    return sorted({ok[i] for i in idx})


def synthetic_uptrend(n=1500, seed=7):
    """Seeded noisy uptrend used when the real history never holds a position."""
    rng = np.random.RandomState(seed)
    r = rng.normal(0.0004, 0.006, n)
    c = 100 * np.exp(np.cumsum(r))
    o = np.r_[c[0], c[:-1]]
    h = np.maximum(o, c) * (1 + np.abs(rng.normal(0, 0.002, n)))
    l = np.minimum(o, c) * (1 - np.abs(rng.normal(0, 0.002, n)))
    idx = pd.date_range("2020-01-01", periods=n, freq="1h", tz="UTC")
    return pd.DataFrame({"open": o, "high": h, "low": l, "close": c, "volume": rng.uniform(50, 150, n)}, index=idx)


def _sig(fn, df, disabled):
    from . import bt
    s, _ = bt.clean_signals(fn(df.copy(), disabled=frozenset(disabled)), df.index)
    return s.values


def check_protective(fn, df, rule, kinds, base_signals=None, scenarios=SCENARIOS):
    """Returns dict(fired: bool, scenarios_tested, fired_in: [...], isolated_fired_in: [...]).
    kinds: {rule_name: 'entry'|'filter'|'exit'|'protective'} (optional; without it only the plain test is possible)."""
    from . import bt
    frames = []
    base = base_signals if base_signals is not None else bt.clean_signals(fn(df.copy()), df.index)[0]
    for t in held_points(base):
        frames.append(("real@%d" % t, df, t))
    if not frames:
        syn = synthetic_uptrend()
        sb = bt.clean_signals(fn(syn.copy()), syn.index)[0]
        frames += [("synthetic@%d" % t, syn, t) for t in held_points(sb)]
    others = [r for r, k in (kinds or {}).items() if r != rule and k in ("exit", "protective")]
    res = {"rule": rule, "frames": len(frames), "tested": 0, "fired_in": [], "isolated_fired_in": [], "notes": []}
    if not frames:
        res["notes"].append("strategy never holds a position on history or synthetic data: cannot exercise the rule")
    for name, d0, t in frames:
        for sc in scenarios:
            d, tt = inject(d0, t, sc)
            res["tested"] += 1
            full = _sig(fn, d, ())
            wo = _sig(fn, d, (rule,))
            if bool(((full[tt + 1:] == 0) & (wo[tt + 1:] == 1)).any()):
                res["fired_in"].append("%s:%s" % (name, sc))
            if others:
                iso_with = _sig(fn, d, others)
                iso_wo = _sig(fn, d, others + [rule])
                if bool(((iso_with[tt + 1:] == 0) & (iso_wo[tt + 1:] == 1)).any()):
                    res["isolated_fired_in"].append("%s:%s" % (name, sc))
    res["fired"] = bool(res["fired_in"] or res["isolated_fired_in"])
    return res
