"""Synthetic-data tests for the US daily v1 simulator and tp.usdata parsing / guards (no network)."""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import usbt  # noqa: E402
from tp import usdata  # noqa: E402


def _panel(n=30, start="1999-12-31"):
    idx = pd.bdate_range(start, periods=n)
    O = pd.DataFrame({"A": np.full(n, 100.0)}, index=idx)
    C = O.copy()
    rf = pd.Series(0.0, index=idx)
    return O, C, rf


def test_flat_prices_cost_only():
    O, C, rf = _panel()
    tgt = pd.DataFrame(np.nan, index=O.index, columns=O.columns)
    tgt.iloc[0] = 1.0
    res = usbt.simulate(tgt, O, C, rf, cost=0.001, start=str(O.index[0].date()))
    # one buy of ~100% notional at 10 bp
    assert res["eq"].iloc[-1] == pytest.approx(1 / 1.001, rel=1e-9)
    assert len(res["fills"]) == 1
    assert res["gross"].iloc[-1] == pytest.approx(1.0)


def test_fill_next_open_not_same_close():
    O, C, rf = _panel()
    C.iloc[1:, 0] = 110.0       # close of day 1 jumps; open of day 1 is 100
    O.iloc[2:, 0] = 110.0
    tgt = pd.DataFrame(np.nan, index=O.index, columns=O.columns)
    tgt.iloc[0] = 1.0           # decided at close day 0 -> filled at OPEN day 1 = 100 -> earns the 10% intraday move
    res = usbt.simulate(tgt, O, C, rf, cost=0.0, start=str(O.index[0].date()))
    assert res["eq"].iloc[1] == pytest.approx(1.10)
    tgt2 = pd.DataFrame(np.nan, index=O.index, columns=O.columns)
    tgt2.iloc[1] = 1.0          # decided at close day 1 (110) -> filled at open day 2 (110) -> no gain
    res2 = usbt.simulate(tgt2, O, C, rf, cost=0.0, start=str(O.index[0].date()))
    assert res2["eq"].iloc[-1] == pytest.approx(1.0)


def test_cash_accrues_rf():
    O, C, rf = _panel(n=11)
    rf[:] = 0.0001
    tgt = pd.DataFrame(np.nan, index=O.index, columns=O.columns)
    res = usbt.simulate(tgt, O, C, rf, start=str(O.index[0].date()))
    assert res["eq"].iloc[-1] == pytest.approx(1.0001 ** 10)


def test_no_drift_retrade_when_fully_invested():
    O, C, rf = _panel(n=40)
    C.iloc[:, 0] = np.linspace(100, 140, 40)
    O.iloc[:, 0] = C.iloc[:, 0].shift(1).fillna(100)
    tgt = pd.DataFrame(1.0, index=O.index, columns=O.columns)   # target 1 every day
    res = usbt.simulate(tgt, O, C, rf, cost=0.0005, start=str(O.index[0].date()))
    assert len(res["fills"]) == 1


def test_episodes_round_trip():
    O, C, rf = _panel(n=10)
    O.iloc[:, 0] = [100, 100, 100, 105, 105, 105, 110, 110, 110, 110]
    C.iloc[:, 0] = O.iloc[:, 0]
    tgt = pd.DataFrame(np.nan, index=O.index, columns=O.columns)
    tgt.iloc[2] = 1.0     # buy at open idx3 = 105
    tgt.iloc[5] = 0.0     # sell at open idx6 = 110
    res = usbt.simulate(tgt, O, C, rf, cost=0.0, start=str(O.index[0].date()))
    ep = usbt.episodes(res["fills"], O, cost=0.0)
    assert ep == [pytest.approx(110 / 105 - 1)]


def test_month_end_flags():
    idx = pd.bdate_range("2020-01-27", "2020-03-04")
    f = usbt.month_end_flags(idx)
    assert list(idx[f.values].strftime("%Y-%m-%d")) == ["2020-01-31", "2020-02-28"]
    f5 = usbt.month_end_flags(idx, 5)
    assert list(idx[f5.values].strftime("%Y-%m-%d")) == ["2020-01-24"][:0] + ["2020-02-21"]


def test_rsi2_bounds():
    s = pd.Series(np.cumsum(np.random.RandomState(0).randn(300)) + 100)
    r = usbt.wilder_rsi(s, 2).dropna()
    assert (r >= 0).all() and (r <= 100).all()


def test_usdata_allowlist():
    with pytest.raises(usdata.FetchError):
        usdata._get("/v1/finance/orders", {})


def test_usdata_parse_and_incomplete_bar():
    import datetime as dt
    ts = [1704205800, 1704292200]   # 2024-01-02, 2024-01-03 09:30 ET
    body = json.dumps({"chart": {"result": [{"timestamp": ts, "events": {"dividends": {"1": {"date": ts[1], "amount": 0.5}}},
                                             "indicators": {"quote": [{"open": [10, 11], "high": [12, 12], "low": [9, 10], "close": [11, 11.5],
                                                                       "volume": [100, 200]}], "adjclose": [{"adjclose": [10.5, 11.5]}]}}]}}).encode()
    now = dt.datetime(2024, 1, 3, 18, 0, tzinfo=dt.timezone.utc)   # 13:00 ET on 01-03: that bar is incomplete
    df, ev = usdata.parse_chart(body, now=now)
    assert list(df.index.strftime("%Y-%m-%d")) == ["2024-01-02"]
    assert ev["dividends"] == [["2024-01-03", 0.5]] or ev["dividends"] == [("2024-01-03", 0.5)]
    adj = usdata.adjusted(df)
    assert adj["close"].iloc[0] == pytest.approx(10.5)
    assert adj["open"].iloc[0] == pytest.approx(10 * 10.5 / 11)


def test_no_order_code_in_usdata():
    src = Path(usdata.__file__).read_text().lower()
    for bad in ("requests.post", "def place", "def order", "submit_order", "api_key", "apikey", "secret"):
        assert bad not in src.replace("no api keys", "").replace("secrets of any kind", "")
