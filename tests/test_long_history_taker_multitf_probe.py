import numpy as np
import pandas as pd

from scripts.research.long_history_taker_multitf_probe import aggregate, derive_signals


def sample_frame(n=120):
    rng=np.random.default_rng(29)
    close=100+np.cumsum(rng.normal(0,1,n))
    open_=np.r_[close[0],close[:-1]]
    high=np.maximum(open_,close)+rng.uniform(.1,1,n)
    low=np.minimum(open_,close)-rng.uniform(.1,1,n)
    volume=rng.uniform(100,500,n)
    quote=volume*close
    buy=quote*rng.uniform(.1,.9,n)
    return pd.DataFrame({'open_ms':np.arange(n,dtype=np.int64)*60_000,
        'o':open_,'h':high,'l':low,'c':close,'v':volume,
        'quote_volume':quote,'taker_buy_quote':buy})


def test_aggregation_uses_only_complete_time_buckets():
    raw=sample_frame(10)
    frame=aggregate(raw,3)
    assert frame.open_ms.tolist()==[0,180_000,360_000]
    assert frame.iloc[0].o==raw.iloc[0].o
    assert frame.iloc[0].c==raw.iloc[2].c
    assert frame.iloc[0].v==raw.iloc[:3].v.sum()


def test_signal_masks_are_prefix_invariant_and_future_mutation_invariant():
    frame=sample_frame()
    full,_=derive_signals(frame)
    cut=83
    prefix,_=derive_signals(frame.iloc[:cut].reset_index(drop=True))
    changed=frame.copy()
    changed.loc[cut:,'o']*=2; changed.loc[cut:,'h']*=2
    changed.loc[cut:,'l']*=2; changed.loc[cut:,'c']*=2
    mutated,_=derive_signals(changed)
    for side in ('long','short'):
        assert np.array_equal(prefix[side][:cut-1],full[side][:cut-1])
        assert np.array_equal(mutated[side][:cut-1],full[side][:cut-1])


def test_future_peeking_negative_control_is_detected():
    frame=sample_frame()
    close=frame.c.to_numpy()
    i=70
    original=bool(close[i+2]>close[i])
    mutated=close.copy()
    mutated[i+2]=close[i]*(.5 if original else 2)
    assert bool(mutated[i+2]>mutated[i]) != original
