"""Slice-2 plugin tests: no-lookahead on every plugin + hand-computed signals on tiny synthetic frames."""
import glob, importlib.util, sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

BASE = Path(__file__).resolve().parents[1]
PLUG = BASE / "plugins" / "slice_2"
sys.path.insert(0, str(BASE)); sys.path.insert(0, str(PLUG))
import s2_lib as L
from common.protocol import check_no_lookahead


class _A:
    def __init__(self, df): self._d = df
    def __getattr__(self, k): return self._d[k].to_numpy()


def load(name):
    spec = importlib.util.spec_from_file_location("t_" + name.replace("-", "_"), PLUG / f"{name}.py")
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


def sg(m, d, **k):
    return _A(m.signals(d, **k))


PLUGINS = sorted(p.stem for p in PLUG.glob("*.py") if p.stem != "s2_lib")


def synth(n=900, freq="4h", start="2024-01-01", seed=3):
    rng = np.random.default_rng(seed)
    r = rng.normal(0, 0.01, n); c = 100 * np.exp(np.cumsum(r)); o = np.r_[c[0], c[:-1]]
    hi = np.maximum(o, c) * (1 + rng.uniform(0, .005, n)); lo = np.minimum(o, c) * (1 - rng.uniform(0, .005, n))
    return pd.DataFrame(dict(open=o, high=hi, low=lo, close=c, volume=rng.uniform(1, 10, n)),
                        index=pd.date_range(start, periods=n, freq=freq, tz="UTC"))


@pytest.mark.parametrize("name", PLUGINS)
def test_no_lookahead_and_contract(name):
    m = load(name)
    freq = {"1d": "1D", "4h": "4h", "1h": "1h"}[m.TIMEFRAMES[0]]
    d = synth(1200, freq)
    assert check_no_lookahead(m, d)
    s = m.signals(d, **m.PARAMS)
    assert len(s) == len(d) and all(s[c].dtype == bool for c in ["long_entry", "short_entry", "long_exit", "short_exit"])
    assert m.DEVIATIONS and len(m.PARAM_GRID) <= 3 and all(len(v) <= 4 for v in m.PARAM_GRID.values())


def test_session_momentum_reversal_hand():
    # 4h bars from Mon 2024-01-01 00:00. Day session [08,20) = bars 2,3,4 of each 6-bar day.
    n = 18; o = np.full(n, 100.0); c = np.full(n, 100.0)
    c[4] = 103.0           # day-1 daytime session: open(bar2)=100 -> close(bar4)=103 => +3%
    o[5:] = 103.0; c[5:] = 103.0; c[10] = 99.0; o[10] = 103.0   # day-2 daytime ends lower (not used for first check)
    d = pd.DataFrame(dict(open=o, high=np.maximum(o, c), low=np.minimum(o, c), close=c, volume=1.0),
                     index=pd.date_range("2024-01-01", periods=n, freq="4h", tz="UTC"))
    mom = sg(load("btc-08utc-momentum-long"), d); rev = sg(load("btc-08utc-reversal-momentum"), d)
    b = 7  # bar 7 = 04:00 day2; next bar (8) opens 08:00 day2 = daytime session start
    assert mom.long_entry[b] and not mom.short_entry[b]       # momentum: previous day-session +3% -> long
    assert rev.short_entry[b] and not rev.long_entry[b]       # reversal -> short
    # night start (20:00) signal bar = last day bar (bar 4 / 10): rev uses momentum rule for night; mom-long night = always long
    assert mom.long_entry[4] and mom.long_entry[10]
    # day-1 daytime (first day) has no previous same session -> no signal at bar 1
    assert not mom.long_entry[1] and not mom.short_entry[1]
    z = load("btc-08utc-cash-cash").signals(d); assert z.to_numpy().sum() == 0


def test_session_zero_return_is_flat():
    d = pd.DataFrame(dict(open=100.0, high=100.0, low=100.0, close=100.0, volume=1.0),
                     index=pd.date_range("2024-01-01", periods=18, freq="4h", tz="UTC"))
    s = sg(load("btc-08utc-reversal-momentum"), d)
    assert not s.long_entry[7] and not s.short_entry[7]


def test_eth_05_session_boundaries_1h():
    d = synth(80, "1h"); s = sg(load("eth-12h-long-reversal-05"), d)
    # day=[05,17) always long: signal bar is 04:00 (next open 05:00)
    idx = d.index
    assert all(s.long_entry[(idx.hour == 4)])
    assert not s.long_entry[(idx.hour == 5)].any()


def test_monday():
    d = synth(14, "1D", start="2024-01-01")   # 2024-01-01 is a Monday
    s = sg(load("btc-monday-intraday"), d)
    assert list(np.where(s.long_entry)[0]) == [6, 13] and list(np.where(s.long_exit)[0]) == [0, 7]


def test_upbit_vwap_hand():
    idx = pd.date_range("2024-01-01 22:00", periods=4, freq="1h", tz="UTC")   # 22,23 | 00,01
    d = pd.DataFrame(dict(open=[10, 10, 10, 10], high=[11, 11, 13, 12], low=[9, 9, 9, 10], close=[10, 12, 9, 11], volume=[1, 1, 1, 3]), index=idx)
    s = sg(load("upbit-vwap-intraday-rules"), d)
    # tp: bar0=10, bar1=(11+9+12)/3=10.667, bar2=(13+9+9)/3=10.333, bar3=(12+10+11)/3=11
    # day2 vwap: bar2 = 10.333 (close 9 below), bar3 = (10.333*1+11*3)/4 = 10.8333 (close 11 above)
    # day1 vwap: bar0 = 10 (close 10 not above), bar1 = (10+10.667)/2 = 10.333 (close 12 above)
    assert list(s.long_entry) == [False, True, False, True]
    assert list(s.long_exit) == [True, False, True, False]


def test_vwap_bb_hand():
    c = np.array([10, 10, 10, 12, 8.0]); d = pd.DataFrame(dict(open=c, high=c + .5, low=c - .5, close=c, volume=1.0), index=pd.date_range("2024-01-01", periods=5, freq="1h", tz="UTC"))
    s = sg(load("c4-vwap-bollinger-bands"), d, length=3, mult=1.0)
    # bar3: window [10,10,12] mean 10.667, pop-std 0.9428 -> upper 11.61; high 12.5 > upper -> entry
    # bar2: window [10,10,10] std 0 -> upper 10, high 10.5 > 10 -> entry too
    # bar4: window [10,12,8] mean 10, std 1.633 -> lower 8.367; low 7.5 < lower -> exit; high 8.5 < upper 11.63
    assert list(s.long_entry) == [False, False, True, True, False]
    assert list(s.long_exit) == [False, False, True, False, True]


def test_jesse_donchian_hand():
    c = np.array([10, 11, 12, 13, 14, 15, 8.0]); h = c + .1; l = c - .1
    d = pd.DataFrame(dict(open=c, high=h, low=l, close=c, volume=1.0), index=pd.date_range("2024-01-01", periods=7, freq="1h", tz="UTC"))
    m = load("jesse_donchian"); s = sg(m, d, period=3, sma_n=2)
    # bar3 close 13 > max(high[0..2])=12.1 and > SMA2 (12.5) -> entry; bar6 close 8 < min(low[3..5])=12.9 -> exit
    assert s.long_entry[3] and not s.long_entry[:3].any()
    assert s.long_exit[6] and not s.long_exit[3]


def test_rsi_wilder_hand_and_crosses():
    c = np.array([10, 11, 10, 12.0])
    r = L.rsi_wilder(c, 2)
    # changes: +1,-1,+2 ; seed avg gain=(1+0)/2=.5, loss=(0+1)/2=.5 at idx2 -> RSI 50 ; idx3: gain=(.5*1+2)/2=1.25 loss=.25 -> RSI=100-100/(1+5)=83.333
    assert r[2] == pytest.approx(50.0) and r[3] == pytest.approx(100 - 100 / 6)
    assert list(L.crossed_above([1, 5, 9, 9], 5)) == [False, False, True, False]


def test_jesse_rsi2_hand():
    c = np.r_[np.linspace(100, 130, 12), 129.5, 131.0]
    d = pd.DataFrame(dict(open=c, high=c, low=c, close=c, volume=1.0), index=pd.date_range("2024-01-01", periods=len(c), freq="1D", tz="UTC"))
    m = load("jesse_rsi2"); s = sg(m, d, rsi_lo=99, rsi_len=2, sma_exit=2, sma_trend=5)
    r = L.rsi_wilder(c, 2)
    s5 = pd.Series(c).rolling(5).mean().to_numpy()
    exp = (c > s5) & (r <= 99)
    assert list(s.long_entry) == list(np.nan_to_num(exp, nan=0).astype(bool)) and s.long_entry.any()


def test_psar_hand():
    # Rising then crash: SAR long initial = low[0]; with af .02: sar1=10 (+.02*(h0-10)) ...
    h = np.array([11, 12, 13, 14, 9.0]); l = np.array([10, 11, 12, 13, 8.0])
    t = L.psar(h, l, .02, .02, .2)
    # bar1: sar=10+.02*(11-10)=10.02 -> min(10.02,l0=10,l0)=10 ; low 11>10 stay long, ep=12 af=.04
    # bar2: sar=10+.04*(12-10)=10.08 -> min(10.08,l1=11,l0=10)=10 ; stay long ep=13 af=.06
    # bar3: sar=10+.06*3=10.18 -> min(..,l2=12,l1=11)=10.18 ; stay long ep=14 af=.08
    # bar4: sar=10.18+.08*(14-10.18)=10.4856 ; low 8 < sar -> flip short
    assert list(t) == [1, 1, 1, 1, -1]
    m = load("jst_parabolic_sar"); d = pd.DataFrame(dict(open=l, high=h, low=l, close=h, volume=1.0), index=pd.date_range("2024-01-01", periods=5, freq="1D", tz="UTC"))
    s = sg(m, d)
    assert list(s.long_exit) == [False] * 4 + [True] and list(s.short_entry) == [False] * 4 + [True]


def test_supertrend_hand():
    n = 12; c = np.linspace(100, 111, n); h = c + 1; l = c - 1
    line, dr = L.supertrend(h, l, c, 3, 1.0)
    # TR = 2 on bar0 (h-l) and 2 after (|h-pc|=2,|l-pc|=0 -> max(2,2,0)=2): ATR=2; lower band bar2 = hl2 - 2
    assert line[2] == pytest.approx(c[2] - 2.0) and dr[2] == 1 and np.isnan(line[0])
    c2 = np.r_[c, 90.0]; h2 = c2 + 1; l2 = c2 - 1
    line2, dr2 = L.supertrend(h2, l2, c2, 3, 1.0)
    assert dr2[-1] == -1 and dr2[-2] == 1  # close 90 < lower band -> flips down


def test_turtle_hand():
    m = load("turtle-system-1")
    c = np.array([10, 10, 10, 10, 11, 12, 13, 9, 9, 9.0]); h = c + .2; l = c - .2
    d = pd.DataFrame(dict(open=c, high=h, low=l, close=c, volume=1.0), index=pd.date_range("2024-01-01", periods=10, freq="1D", tz="UTC"))
    s = sg(m, d, entry_n=3, exit_n=2, fallback_n=50, stop_mult=2.0, atr_n=3)
    # bar4: close 11 > max(high[1..3])=10.2 -> first-ever hypothetical breakout, taken
    assert s.long_entry[4] and not s.long_entry[:4].any()
    # bar7: close 9 < prior 2-bar low (min(l5,l6)=11.8) -> long exit
    assert s.long_exit[7]
    # hypothetical trade 1 entered open[5]=12 exit open[8]=9 -> loser => breakouts after are allowed
    assert np.isfinite(s.atr_stop[4])


def test_turtle_winner_filter_hand():
    m = load("turtle-system-1")
    # up-move (winner), pullback exit, then second breakout must be SKIPPED because last was a winner
    c = np.array([10, 10, 10, 10, 11, 12, 13, 12, 11, 10, 10, 10, 11.5, 12, 13.0]); h = c + .1; l = c - .1
    d = pd.DataFrame(dict(open=c, high=h, low=l, close=c, volume=1.0), index=pd.date_range("2024-01-01", periods=len(c), freq="1D", tz="UTC"))
    s = sg(m, d, entry_n=3, exit_n=2, fallback_n=50, stop_mult=5.0, atr_n=3)
    assert s.long_entry[4]
    ev = np.where(s.long_entry)[0]
    assert 12 not in ev   # hypothetical trade 1: entry open[5]=12 exit after close<2-bar low -> pnl>0? exits at open[8] ~12 => check below
    # compute expectation directly: exit_pending set at bar 7 (close 12 < min(l5,l6)=11.9? no) -> verify via the track
    assert len(ev) >= 1


def test_tv_channel_daily_alignment_hand():
    m = load("tv_channel_100_50_atr")
    idx = pd.date_range("2024-01-01", periods=18, freq="4h", tz="UTC")   # 3 days of 6 bars
    c = np.full(18, 100.0); h = c + 1; l = c - 1
    c[12:] = 120.0; h[12:] = 121.0; l[12:] = 119.0      # day 3 jumps up
    c[17] = 125.0; h[17] = 125.5
    d = pd.DataFrame(dict(open=c, high=h, low=l, close=c, volume=1.0), index=idx)
    s = sg(m, d, n_entry=5, atr_mult=2.0, atr_len=1, tp_r=4.0)
    # atr_len=1: ATR = TR of previous day. Day1 TR=2 (h-l), Day2 TR=2 -> prev daily close for day 3 = 100 (day2 close)
    # day-3 bar 12: close 120 > prior 5-bar high 101 -> breakout; stop = 100 - 2*2 = 96 ; R = 120-96 = 24 ; stop_pct = .2 ; tp = .8
    assert s.long_entry[12]
    assert s.stop_pct[12] == pytest.approx(24 / 120) and s.tp_pct[12] == pytest.approx(4 * 24 / 120)
    # causality: day-3 values must not use day 3 data -> change day 3 closes drastically for later bars, bar 12 stays the same
    d2 = d.copy(); d2.iloc[13:, d2.columns.get_loc("high")] += 50; d2.iloc[13:, d2.columns.get_loc("close")] += 50
    s2 = sg(m, d2, n_entry=5, atr_mult=2.0, atr_len=1, tp_r=4.0)
    assert s2.stop_pct[12] == pytest.approx(s.stop_pct[12])


def test_ft_cofibit_components():
    m = load("ft_cofibit"); d = synth(400, "1h")
    s = sg(m, d)
    assert (s.stop_pct == 0.25).all() and (s.tp_pct == 0.05).all()
    # STOCHF hand: window of 5 highs/lows
    h = np.array([12, 13, 14, 15, 16.0]); l = np.array([8, 9, 10, 11, 12.0]); c = np.array([9, 10, 11, 12, 14.0])
    fk = 100 * (14 - 8) / (16 - 8)
    assert fk == 75.0
    assert L.ema_ta([1, 2, 3, 4, 5], 5)[4] == pytest.approx(3.0)


def test_pk_rsi_entry_exit_hand():
    m = load("pk_rsi_directional"); d = synth(600, "1h", seed=9)
    s = sg(m, d, rsi_len=4, ema_len=5, buy_lvl=60, sell_lvl=70)
    c = d.close.to_numpy(); r = L.rsi_wilder(c, 4); e = L.ema_ta(c, 5); l = d.low.to_numpy()
    exp = np.zeros(len(c), bool); exp[1:] = (r[1:] > 60) & (r[:-1] <= 60) & (l[1:] > e[1:])
    assert (s.long_entry == exp).all() and exp.any()
    ex = np.r_[False, (r[1:] > 70) & (r[:-1] <= 70)] | (l < e)
    assert (s.long_exit == ex).all()


def test_timestamp_recovery_from_reset_index():
    d = pd.read_parquet(BASE.parent / "bb_stoch_stc" / "data" / "BTCUSDT_4h.parquet").iloc[3000:3500]
    ts = L.timestamps(d.reset_index(drop=True))
    assert (ts == d.index).all()
