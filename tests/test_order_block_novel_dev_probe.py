import numpy as np
import pandas as pd

from scripts.research.order_block_novel_dev_probe import (
    breaker_signals,
    form_zones,
    htf_mitigation_signals,
)


def frame_from_close(close, opens=None, lows=None, highs=None, start=0, step=60_000):
    close=np.asarray(close,dtype=float)
    opens=close.copy() if opens is None else np.asarray(opens,dtype=float)
    lows=np.minimum(opens,close)-0.05 if lows is None else np.asarray(lows,dtype=float)
    highs=np.maximum(opens,close)+0.05 if highs is None else np.asarray(highs,dtype=float)
    return pd.DataFrame({"t_open_ms":start+np.arange(len(close))*step,"o":opens,"h":highs,
                         "l":lows,"c":close,"v":np.ones(len(close)),
                         "quote_v":np.ones(len(close)),"trades":np.ones(len(close),dtype=int)})


def test_breaker_signal_is_prefix_invariant():
    rng=np.random.default_rng(7)
    close=100+np.cumsum(rng.normal(0,0.3,900))
    open_=close-rng.normal(0,0.15,900)
    f=frame_from_close(close,open_)
    full=breaker_signals(f)
    cut=530
    prefix=breaker_signals(f.iloc[:cut].reset_index(drop=True))
    assert [s for s in full if s["signal_index"]<cut]==prefix


def test_htf_features_only_use_closed_bars_and_emit_ltf_indices():
    # 5m resampling requires exact complete buckets; returned indices must map
    # to the source 1m frame and can never precede an HTF close.
    rng=np.random.default_rng(13)
    close=100+np.cumsum(rng.normal(0,0.25,3000))
    op=close-rng.normal(0,0.2,3000)
    f=frame_from_close(close,op)
    signals=htf_mitigation_signals(f,width=5)
    assert all(0 < s["signal_index"] < len(f) for s in signals)
    assert all(s["hypothesis"]=="htf_first_mitigation" for s in signals)
    assert all(s["stop"] < f.c.iloc[s["signal_index"]] if s["signal_side"]=="long"
               else s["stop"] > f.c.iloc[s["signal_index"]] for s in signals)


def test_zone_formation_is_causal_under_future_mutation():
    rng=np.random.default_rng(31)
    close=100+np.cumsum(rng.normal(0,0.4,500))
    op=close-rng.normal(0,0.2,500)
    f=frame_from_close(close,op)
    altered=f.copy()
    altered.loc[300:, ["o","h","l","c"]] *= 4
    cutoff=300
    left=[z for z in form_zones(f) if z["born"]<cutoff]
    right=[z for z in form_zones(altered) if z["born"]<cutoff]
    assert left==right
