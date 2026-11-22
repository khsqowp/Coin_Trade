import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from forward_test.config import JBB_1H, get_profile
from forward_test.engine import Engine
from forward_test.plugin_jbb import signals as vendored_signals
from forward_test.status import status_data

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "scratchpad/bb_stoch_stc/data"
PLUGIN_PATH = ROOT / "scratchpad/strategy_bt/plugins/slice_3/jesse_simple_bollinger.py"
BT = ROOT / "scratchpad/strategy_bt"


def load_source_plugin():
    sys.path.insert(0, str(BT))
    spec = importlib.util.spec_from_file_location("source_jbb", PLUGIN_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("symbol", ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT"])
def test_vendored_signals_match_source_on_cached_data(symbol):
    path = DATA / f"{symbol}_1h.parquet"
    if not path.exists():
        pytest.skip(f"scratchpad cache unavailable: {path}")
    frame = pd.read_parquet(path)
    source = load_source_plugin()
    expected = source.signals(frame, **JBB_1H.signal)
    actual = vendored_signals(frame, **JBB_1H.signal)
    pd.testing.assert_frame_equal(actual, expected)


def longest_contiguous(frame):
    breaks = np.flatnonzero(np.diff(frame.index.as_unit("ns").asi8) != JBB_1H.interval_ms * 1_000_000) + 1
    bounds = np.r_[0, breaks, len(frame)]
    lo, hi = max(zip(bounds[:-1], bounds[1:]), key=lambda pair: pair[1] - pair[0])
    return frame.iloc[lo:hi]


def test_jbb_replay_equivalence_and_restart_idempotence(tmp_path):
    path = DATA / "BTCUSDT_1h.parquet"
    if not path.exists():
        pytest.skip("scratchpad BTC 1h cache unavailable")
    sys.path.insert(0, str(BT))
    from common.engine import simulate

    frame = longest_contiguous(pd.read_parquet(path))
    if len(frame) < 400:
        pytest.skip("cached contiguous BTC 1h segment is too short")
    cut = len(frame) // 2
    forward = frame.iloc[cut:]
    start = int(forward.index[0].timestamp() * 1000)
    source = load_source_plugin()
    full_signals = source.signals(frame, **JBB_1H.signal)
    test_signals = full_signals.iloc[cut:]
    expected, _ = simulate(forward, test_signals, side="long", capital=JBB_1H.capital,
                           base_notional=JBB_1H.base_notional, fee=JBB_1H.fee,
                           slippage=JBB_1H.slippage)
    expected = [trade for trade in expected if trade["exit"] < len(forward) - 1]

    db_path = tmp_path / "jbb.db"
    engine = Engine(db_path, profile=JBB_1H)
    engine.put_candles("BTCUSDT", frame)
    engine.db.execute("INSERT INTO meta VALUES('forward_start_ts',?)", (str(start),))
    engine.db.commit()
    engine.run()
    actual = engine.db.execute("SELECT * FROM trades WHERE book='long_only' ORDER BY entry_ts").fetchall()
    assert len(actual) == len(expected)
    for got, want in zip(actual, expected):
        assert got["entry_ts"] == int(forward.index[want["entry"]].timestamp() * 1000)
        assert got["exit_ts"] == int(forward.index[want["exit"]].timestamp() * 1000)
        assert got["side"] == "long" and got["reason"] == want["reason"]
        assert got["bars"] == want["bars"]
        expected_entry = float(forward.iloc[want["entry"]].open) * (1 + JBB_1H.slippage)
        expected_exit = float(forward.iloc[want["exit"]].open) * (1 - JBB_1H.slippage)
        assert np.isclose(got["entry_px"], expected_entry, rtol=0, atol=1e-10)
        assert np.isclose(got["exit_px"], expected_exit, rtol=0, atol=1e-10)
        assert np.isclose(got["net_pnl"], want["net"], rtol=0, atol=1e-8)
    count = engine.db.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
    engine.run()
    restarted = Engine(db_path, profile=JBB_1H)
    restarted.run()
    assert restarted.db.execute("SELECT COUNT(*) FROM trades").fetchone()[0] == count
    assert restarted.db.execute("SELECT COUNT(*) FROM trades WHERE entry_ts<?", (start,)).fetchone()[0] == 0


def test_jbb_configuration_and_status_reference(tmp_path):
    profile = get_profile("jbb_1h")
    assert profile.interval == "1h" and profile.interval_ms == 3_600_000
    assert profile.kind == "plugin" and profile.books == ("long_only",)
    assert profile.initial_history_days == 60
    engine = Engine(tmp_path / "status.db", profile=profile)
    data = status_data(engine.db, profile=profile)
    assert data["books"]["combined"] == data["books"]["long_only"]
    assert data["progress"]["minimum_trades"] == 100
    assert data["progress"]["minimum_days"] == 60
    assert data["progress"]["verdict"] == "INSUFFICIENT DATA"
    assert data["progress"]["backtest_reference"]["test_trades"] == 885
    assert "not a proven edge" in data["progress"]["caveat"]
