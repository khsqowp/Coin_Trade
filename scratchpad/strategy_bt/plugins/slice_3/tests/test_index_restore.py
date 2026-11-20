"""RangeIndex train/test slices (as passed by common.protocol.evaluate) must give the same
signals as the original DatetimeIndex frame, including across the 2023-03-24 1h/15m data gap."""
import importlib.util
from pathlib import Path
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT.parents[2] / "bb_stoch_stc" / "data"
CASES = [("btc-08utc-momentum-reversal", "1h"), ("eth-day-reversal-night-cash-05", "1h"),
         ("four-lower-high-break-intraday", "1h"), ("c4-upbit-larry-williams-k05-volatility-breakout", "15m"),
         ("jesse_dual_thrust", "1h")]

def load(sid):
    s = importlib.util.spec_from_file_location(sid.replace("-", "_"), ROOT / f"{sid}.py")
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m

@pytest.mark.parametrize("sid,tf", CASES)
def test_rangeindex_slices_match_datetime_signals(sid, tf):
    p = load(sid); df = pd.read_parquet(DATA / f"ETHUSDT_{tf}.parquet"); k = int(len(df) * .6)
    cols = ["long_entry", "short_entry", "long_exit", "short_exit"]
    train = p.signals(df.iloc[:k].reset_index(drop=True), **p.PARAMS)[cols].to_numpy()
    ref = p.signals(df.iloc[:k], **p.PARAMS)[cols].to_numpy()
    assert (train == ref).all()
    test = p.signals(df.iloc[k:].reset_index(drop=True), **p.PARAMS)[cols].to_numpy()
    ref2 = p.signals(df.iloc[k:], **p.PARAMS)[cols].to_numpy()
    assert (test == ref2).all()
