import numpy as np
import pandas as pd
import pytest

from chart_predictor import mtf_forward
from chart_predictor.setups import Signal


def candle_prefix(minutes=7_201):
    stamps = np.arange(minutes, dtype=np.int64) * 60_000
    close = 100.0 + np.sin(np.arange(minutes) / 17.0) * 0.2
    return pd.DataFrame({
        "t_open_ms": stamps,
        "o": close,
        "h": close + 0.3,
        "l": close - 0.3,
        "c": close,
        "v": np.ones(minutes),
        "quote_v": np.ones(minutes) * 100,
        "trades": np.ones(minutes, dtype=np.int64),
    })


def latest_bar_long(frame, setup, prepared=None):
    if len(frame) < 2:
        return []
    return [Signal(index=len(frame) - 2, side="long", stop=99.0)]


def test_forward_forecast_uses_only_closed_prefix_and_requires_distinct_fresh_votes(monkeypatch):
    monkeypatch.setattr(mtf_forward, "generate_signals", latest_bar_long)
    entry_ms = 7_200 * 60_000
    raw = candle_prefix()
    result = mtf_forward.forecast_at(
        raw, symbol="BTCUSDT", entry_ms=entry_ms, entry_price=100.0
    )

    assert result["status"] == "EMITTED"
    assert result["event"]["side"] == "long"
    assert len(result["event"]["forecasts"]) >= 2
    assert all(vote["signal_close_ms"] <= entry_ms
               for vote in result["event"]["forecasts"].values())
    assert result["input_prefix_end_ms"] == entry_ms - 60_000
    assert len(result["input_prefix_sha256"]) == 64


def test_future_rows_and_unfinished_current_minute_cannot_change_forecast(monkeypatch):
    monkeypatch.setattr(mtf_forward, "generate_signals", latest_bar_long)
    entry_ms = 7_200 * 60_000
    prefix = candle_prefix()
    first = mtf_forward.forecast_at(
        prefix, symbol="BTCUSDT", entry_ms=entry_ms, entry_price=100.0
    )

    future = pd.concat([
        prefix,
        pd.DataFrame([{
            "t_open_ms": entry_ms, "o": 100.0, "h": 1e12, "l": 1e-12,
            "c": 1e12, "v": 1e12, "quote_v": 1e12, "trades": 1,
        }]),
    ], ignore_index=True)
    second = mtf_forward.forecast_at(
        future, symbol="BTCUSDT", entry_ms=entry_ms, entry_price=100.0
    )

    assert second == first


def test_forward_forecast_abstains_on_any_minute_gap_before_anchor(monkeypatch):
    monkeypatch.setattr(mtf_forward, "generate_signals", latest_bar_long)
    entry_ms = 7_200 * 60_000
    raw = candle_prefix().drop(index=100).reset_index(drop=True)

    result = mtf_forward.forecast_at(
        raw, symbol="BTCUSDT", entry_ms=entry_ms, entry_price=100.0
    )

    assert result["status"] == "ABSTAIN_DATA_GAP"
    assert result["missing_open_ms"] == 100 * 60_000


def test_forward_forecast_respects_per_timeframe_overlap_deadlines(monkeypatch):
    monkeypatch.setattr(mtf_forward, "generate_signals", latest_bar_long)
    entry_ms = 7_200 * 60_000
    blocked_until = {
        timeframe: entry_ms + 1
        for timeframe in mtf_forward.TIMEFRAME_MINUTES
    }

    result = mtf_forward.forecast_at(
        candle_prefix(), symbol="BTCUSDT", entry_ms=entry_ms,
        entry_price=100.0, blocked_until=blocked_until,
    )

    assert result["status"] == "ABSTAIN_OVERLAP"
    assert result["event"] is None


@pytest.mark.parametrize("entry_ms,entry_price", [
    (7_200 * 60_000 + 1, 100.0),
    (7_200 * 60_000, 0.0),
])
def test_forward_forecast_rejects_invalid_entry_anchor(entry_ms, entry_price):
    with pytest.raises(ValueError):
        mtf_forward.forecast_at(
            candle_prefix(), symbol="BTCUSDT", entry_ms=entry_ms,
            entry_price=entry_price,
        )
