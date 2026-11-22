"""Causal 12-hour session allocation rule from the archived specification."""
import numpy as np
import pandas as pd

SPEC_ID = 'btc-08utc-short-reversal'
PARAMS = {"h": 8}
PARAM_GRID = {}
TIMEFRAMES = ["1h"]
SIDES = "both"
DEVIATIONS = [
    "Harness applies entries to all five primary majors; archived instrument restriction (BTCUSD or ETHUSD) cannot be enforced by this plugin.",
    "Harness uses fixed notional and charges its fee/slippage per session leg; paper unit-notional sizing and excluded trading costs are not reproduced.",
    "Harness reset_index(drop=True) removes UTC timestamps in train/test slices (HARNESS_ISSUES.md #1); timestamps are restored from the shared cached BTCUSDT index when slice length equals the full/60%/40% length of the 15m/1h/4h cache (only timestamps recovered, real gaps preserved). The TEST slice has no preceding-day/session history, so the first prior-session/prior-day dependent decisions are flat/absent.",
    "Session return is computed literally as last hourly close divided by first hourly open minus one; no separate boundary price series is available.",
    "The signal is emitted on the bar immediately before session start and fills at the next hourly open; max_hold=11 closes at the last session bar close, the harness representation of the session boundary.",
    "A missing or zero previous same-type session return maps to cash; incomplete 12-bar sessions are discarded.",
    "max_hold counts observed rows; missing hourly bars during a held session can move the final-bar close past the UTC session boundary, and the upcoming session cannot be prevalidated without lookahead.",
]
IMPLEMENTED_FIELDS = ["entry_long", "entry_short", "exit", "filters", "timeframes"]

def _utc_index(df):
    """Return the UTC bar-open DatetimeIndex of df.
    Workaround for HARNESS_ISSUES.md #1: common.protocol.evaluate() resets the index of the
    train/test slices to a RangeIndex. The cached 15m/1h/4h parquet files of every symbol share
    one identical, gap-containing index, so a RangeIndex slice whose length equals the full /
    first-60% / last-40% length of a cached reference file is mapped back onto that reference
    index (only timestamps are recovered; no price information from the reference is used)."""
    from pathlib import Path
    idx = df.index
    if isinstance(idx, pd.DatetimeIndex):
        return idx.tz_localize("UTC") if idx.tz is None else idx.tz_convert("UTC")
    n = len(df)
    here = Path(__file__).resolve()
    for base in here.parents:
        data = base / "bb_stoch_stc" / "data"
        if not data.is_dir():
            data = base.parent / "bb_stoch_stc" / "data"
        if data.is_dir():
            break
    else:
        raise RuntimeError("cannot locate bb_stoch_stc/data to restore timestamps")
    for tf in ("15m", "1h", "4h"):
        ref = pd.read_parquet(data / f"BTCUSDT_{tf}.parquet", columns=["close"]).index
        full = len(ref); tr = int(full * 0.6)
        for length, part in ((full, ref), (tr, ref[:tr]), (full - tr, ref[tr:])):
            if n == length:
                return pd.DatetimeIndex(part)
    raise ValueError("UTC index was removed and slice length matches no cached 15m/1h/4h split")

# Each bar is assigned to its 12h session by its UTC open timestamp. A session
# return is usable only when all 12 consecutive hourly bars are present.
def signals(df, h=8):
    n = len(df)
    out = pd.DataFrame({"long_entry": np.zeros(n, dtype=bool),
                        "short_entry": np.zeros(n, dtype=bool),
                        "long_exit": np.zeros(n, dtype=bool),
                        "short_exit": np.zeros(n, dtype=bool),
                        "max_hold": np.full(n, np.nan)}, index=df.index)
    if n == 0:
        return out
    idx = _utc_index(df)
    ns = idx.as_unit("ns").asi8
    hour_ns = 3_600_000_000_000
    day_ns = 24 * hour_ns
    origin = int(pd.Timestamp("1970-01-01", tz="UTC").value) + h * hour_ns
    starts = origin + np.floor_divide(ns - origin, 12 * hour_ns) * (12 * hour_ns)
    frame = pd.DataFrame({"start": starts, "ts": ns,
                          "open": df["open"].to_numpy(float),
                          "close": df["close"].to_numpy(float)})
    grouped = frame.groupby("start", sort=True)
    stats = grouped.agg(count=("ts", "size"), unique_ts=("ts", "nunique"), first_ts=("ts", "min"), last_ts=("ts", "max"),
                        first_open=("open", "first"), last_close=("close", "last"))
    complete = ((stats["count"] == 12) & (stats["unique_ts"] == 12) & (stats["last_ts"] - stats["first_ts"] == 11 * hour_ns))
    stats["ret"] = np.where(complete, stats["last_close"] / stats["first_open"] - 1.0, np.nan)
    start_index = stats.index.to_numpy(np.int64)
    type_hour = ((start_index - origin) // (12 * hour_ns)) % 2
    previous = stats["ret"].groupby(type_hour).transform(lambda values: values.ffill().shift(1))
    # Map each start to its previous completed return of the same session type.
    prev_by_start = dict(zip(start_index.tolist(), previous.to_numpy().tolist()))
    # The last bar of each session signals the next session; fill is its open.
    candidate = ns == starts + 11 * hour_ns
    rows = np.flatnonzero(candidate)
    if len(rows):
        row_starts = starts[rows] + 12 * hour_ns
        prev_vals = np.array([prev_by_start.get(int(st), np.nan) for st in row_starts], dtype=float)
        session_types = ((row_starts - origin) // (12 * hour_ns)) % 2
        prior_signs = np.sign(np.where(np.isfinite(prev_vals), prev_vals, 0.0))
        directions = np.array([_direction(int(t), float(s)) for t, s in zip(session_types, prior_signs)], dtype=float)
        out.iloc[rows, 0] = directions > 0
        out.iloc[rows, 1] = directions < 0
        out.iloc[rows, 4] = np.where(directions != 0, 11.0, np.nan)
    return out

def _direction(session_type, prior_sign):
    # session_type=0 is D(h), 1 is N; concrete rules are substituted below.
    return -1 if session_type == 0 else -prior_sign
