import importlib.util
from pathlib import Path
import sys
import numpy as np
import pandas as pd
import pytest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
PLUGIN_DIR=ROOT/"plugins"/"slice_0"
from common.protocol import check_no_lookahead

PLUGIN_NAMES=["btc-08utc-cash-short","btc-08utc-long-reversal","btc-08utc-momentum-short",
              "btc-08utc-short-cash","btc-08utc-short-short","eth-night-momentum-day-cash-05",
              "btc-max10-nyse-close"]
def load(name):
    spec=importlib.util.spec_from_file_location("plugin_"+name,PLUGIN_DIR/(name+".py"))
    mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); return mod

def random_ohlc(index,seed=31):
    rng=np.random.default_rng(seed); close=100*np.exp(np.cumsum(rng.normal(0,.01,len(index))))
    return pd.DataFrame({"open":close*(1+rng.normal(0,.001,len(index))),"high":close*1.01,
                         "low":close*.99,"close":close},index=index)

@pytest.mark.parametrize("name",PLUGIN_NAMES)
def test_no_lookahead(name):
    mod=load(name); tf="15min" if name.endswith("nyse-close") else "h"
    idx=pd.date_range("2024-01-01",periods=600,freq=tf,tz="UTC")
    assert check_no_lookahead(mod,random_ohlc(idx))

def test_session_momentum_hand_computed_bar():
    mod=load("eth-night-momentum-day-cash-05")
    idx=pd.date_range("2024-01-01 00:00",periods=72,freq="h",tz="UTC")
    df=pd.DataFrame({"open":100.,"high":101.,"low":99.,"close":100.},index=idx)
    # The completed Jan 1 night session is bars 17..28; its return is +10%.
    df.loc[idx[17:29],"close"]=[100.5]*11+[110.]
    got=mod.signals(df)
    # Jan 2 16:00 (index 40) signals the Jan 2 17:00 night entry from that prior return.
    assert got.short_entry.iloc[40] == False
    assert got.long_entry.iloc[40] == True
    assert got.max_hold.iloc[40] == 11

def test_nyse_calendar_dst_and_hand_computed_high():
    mod=load("btc-max10-nyse-close")
    assert pd.Timestamp("2023-04-07").date() in mod.nyse_holidays(2023)
    assert pd.Timestamp("2023-07-04").date() in mod.nyse_holidays(2023)
    assert pd.Timestamp("2022-06-20").date() in mod.nyse_holidays(2022)
    assert pd.Timestamp("2022-06-17").date() not in mod.nyse_holidays(2022)
    from zoneinfo import ZoneInfo
    et=ZoneInfo("America/New_York")
    assert pd.Timestamp("2024-07-01 16:00",tz=et).tz_convert("UTC").hour==20
    assert pd.Timestamp("2024-01-02 16:00",tz=et).tz_convert("UTC").hour==21
    dates=pd.bdate_range("2024-01-02",periods=11)
    # Skip the weekend naturally; observation close is 16:00 ET and only the last is a new high.
    opens=[pd.Timestamp(d.date(),tz="America/New_York")+pd.Timedelta(hours=15,minutes=45) for d in dates]
    idx=pd.DatetimeIndex(opens).tz_convert("UTC")
    vals=np.arange(100.,111.)
    df=pd.DataFrame({"open":vals,"high":vals+1,"low":vals-1,"close":vals},index=idx)
    sig=mod.signals(df)
    assert np.flatnonzero(sig.long_entry).tolist()==[10]

def test_real_data_smoke_and_reset_index_recovery():
    data=ROOT.parent/"bb_stoch_stc"/"data"
    if not (data/"BTCUSDT_1h.parquet").exists(): pytest.skip("BTCUSDT hourly parquet unavailable")
    hourly=pd.read_parquet(data/"BTCUSDT_1h.parquet").iloc[3000:9000]
    for name in PLUGIN_NAMES[:6]:
        out=load(name).signals(hourly)
        assert len(out)==len(hourly) and (out.long_entry|out.short_entry).any()
    session=load(PLUGIN_NAMES[2])
    pd.testing.assert_frame_equal(session.signals(hourly).reset_index(drop=True),session.signals(hourly.reset_index(drop=True)))
    if (data/"BTCUSDT_15m.parquet").exists():
        quarter=pd.read_parquet(data/"BTCUSDT_15m.parquet").iloc[3000:9000]
        max10=load("btc-max10-nyse-close")
        assert (max10.signals(quarter).long_entry).any()
        pd.testing.assert_frame_equal(max10.signals(quarter).reset_index(drop=True),max10.signals(quarter.reset_index(drop=True)))
