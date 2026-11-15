import numpy as np
import pandas as pd
import pytest

from chart_predictor.mtf_consensus import build_consensus, score_forecast


def signal(symbol, timeframe, side, close_ms, stop, setup="bb_squeeze_breakout"):
    return {"symbol": symbol, "timeframe": timeframe, "side": side,
            "signal_close_ms": close_ms, "stop": stop, "setup": setup}


def forecast(side="long", timeframe="1m", stop=99.0, target=102.0):
    return {"symbol": "BTCUSDT", "timeframe": timeframe, "side": side,
            "entry_ms": 120_000, "entry_price": 100.0,
            "stop": stop, "target": target}


def minute_frame(count=20):
    times = 120_000 + np.arange(count) * 60_000
    return pd.DataFrame({"t_open_ms": times, "o": 100.0, "h": 100.5,
                         "l": 99.5, "c": 100.0})


def test_consensus_requires_two_fresh_distinct_timeframes_and_builds_each_risk():
    rows = [signal("BTCUSDT", "1m", "long", 120_000, 99.0),
            signal("BTCUSDT", "5m", "long", 0, 98.0)]
    result = build_consensus(rows, symbol="BTCUSDT", entry_ms=120_000,
                             entry_price=100.0)
    assert result["side"] == "long"
    assert set(result["forecasts"]) == {"1m", "5m"}
    assert result["forecasts"]["1m"]["target"] == 102.0
    assert result["forecasts"]["5m"]["target"] == 104.0


def test_consensus_abstains_on_cross_timeframe_or_same_timeframe_conflict():
    opposing = [signal("BTCUSDT", "1m", "long", 120_000, 99),
                signal("BTCUSDT", "5m", "short", 0, 101)]
    assert build_consensus(opposing, symbol="BTCUSDT", entry_ms=120_000,
                           entry_price=100) is None

    same_tf = [signal("BTCUSDT", "1m", "long", 120_000, 99),
               signal("BTCUSDT", "1m", "short", 120_000, 101, "vwap_band_fade"),
               signal("BTCUSDT", "5m", "long", 0, 99),
               signal("BTCUSDT", "30m", "long", 0, 99)]
    assert build_consensus(same_tf, symbol="BTCUSDT", entry_ms=120_000,
                           entry_price=100) is None


def test_consensus_rejects_stale_future_wrong_symbol_and_invalidated_votes():
    rows = [signal("BTCUSDT", "1m", "long", 0, 99),
            signal("BTCUSDT", "5m", "long", 0, 99),
            signal("ETHUSDT", "30m", "long", 120_000, 99),
            signal("BTCUSDT", "30m", "short", 1_800_000, 101)]
    assert build_consensus(rows, symbol="BTCUSDT", entry_ms=360_000,
                           entry_price=100) is None

    crossed_stop = [signal("BTCUSDT", "1m", "long", 120_000, 100),
                    signal("BTCUSDT", "5m", "long", 0, 99)]
    assert build_consensus(crossed_stop, symbol="BTCUSDT", entry_ms=120_000,
                           entry_price=100) is None


def test_consensus_abstains_when_short_two_r_target_is_not_a_valid_price():
    rows = [signal("BTCUSDT", "1m", "short", 120_000, 160.0),
            signal("BTCUSDT", "5m", "short", 0, 101.0)]
    assert build_consensus(rows, symbol="BTCUSDT", entry_ms=120_000,
                           entry_price=100.0) is None


def test_consensus_is_invariant_to_signals_after_entry_time():
    prefix = [signal("BTCUSDT", "1m", "long", 120_000, 99),
              signal("BTCUSDT", "5m", "long", 0, 98)]
    future_mutated = prefix + [signal("BTCUSDT", "30m", "short", 120_001, float("nan"))]
    kwargs = {"symbol": "BTCUSDT", "entry_ms": 120_000, "entry_price": 100}
    assert build_consensus(prefix, **kwargs) == build_consensus(future_mutated, **kwargs)


def test_target_first_fees_and_same_minute_tie_are_conservative():
    frame = minute_frame()
    frame.loc[2, "h"] = 102.1
    result = score_forecast(forecast(), frame)
    assert result["10_bars"]["outcome"] == "TARGET"
    assert result["20_bars"]["target_first"] is True
    assert result["10_bars"]["net_r"] == pytest.approx(1.9)
    assert result["leverage"]["4x"]["10_bars"]["net_return"] == pytest.approx(.076)
    assert result["leverage"]["5x"]["10_bars"]["net_return"] == pytest.approx(.095)

    frame.loc[2, ["h", "l"]] = [102.1, 98.9]
    tied = score_forecast(forecast(), frame)
    assert tied["10_bars"]["outcome"] == "STOP"
    assert tied["20_bars"]["target_first"] is False
    assert tied["10_bars"]["net_r"] == pytest.approx(-1.1)


def test_unleveraged_scoring_can_skip_leverage_paths_without_changing_outcomes():
    frame = minute_frame()
    frame.loc[2, "h"] = 102.1
    full = score_forecast(forecast(), frame)
    fast = score_forecast(forecast(), frame, include_leverage=False)
    assert fast["10_bars"] == full["10_bars"]
    assert fast["20_bars"] == full["20_bars"]
    assert fast["leverage"] == {}


def test_checkpoints_are_independent_and_future_bars_do_not_change_scores():
    frame = minute_frame(20)
    frame.loc[12, "h"] = 102.1
    result = score_forecast(forecast(), frame)
    assert result["10_bars"]["outcome"] == "TIMEOUT"
    assert result["20_bars"]["outcome"] == "TARGET"

    longer = pd.concat([frame, minute_frame(1).assign(t_open_ms=1_320_000,
                       o=1_000_000, h=2_000_000, l=1, c=1_000_000),
                       minute_frame(1).assign(t_open_ms=np.nan, o=np.nan, h=np.nan,
                       l=np.nan, c=np.nan)], ignore_index=True)
    assert score_forecast(forecast(), longer) == result


def test_short_side_uses_symmetric_target_and_five_minute_deadlines():
    frame = minute_frame(100)
    frame.loc[54, "l"] = 97.9
    result = score_forecast(forecast("short", "5m", 101.0, 98.0), frame)
    assert result["10_bars"]["outcome"] == "TIMEOUT"
    assert result["10_bars"]["horizon_bars"] == 10
    assert result["20_bars"]["outcome"] == "TARGET"
    assert result["20_bars"]["net_r"] == pytest.approx(1.9)


def test_leverage_specific_liquidation_precedes_a_wide_planned_stop():
    frame = minute_frame()
    frame.loc[2, "l"] = 79.0
    result = score_forecast(forecast(stop=80.0, target=140.0), frame)
    assert result["10_bars"]["outcome"] == "STOP"
    assert result["leverage"]["4x"]["10_bars"]["outcome"] == "STOP"
    assert result["leverage"]["5x"]["10_bars"]["outcome"] == "LIQUIDATION"
    assert result["leverage"]["5x"]["10_bars"]["exit_price"] == pytest.approx(80.5)

    short_frame = minute_frame()
    short_frame.loc[2, "h"] = 121.0
    short = score_forecast(forecast("short", "1m", 120.0, 60.0), short_frame)
    assert short["leverage"]["4x"]["10_bars"]["outcome"] == "STOP"
    assert short["leverage"]["5x"]["10_bars"]["outcome"] == "LIQUIDATION"
    assert short["leverage"]["5x"]["10_bars"]["exit_price"] == pytest.approx(119.5)


def test_gap_and_incomplete_horizon_are_not_scored_as_losses_or_timeouts():
    frame = minute_frame()
    gap = frame.drop(index=4).reset_index(drop=True)
    result = score_forecast(forecast(), gap)
    assert result["10_bars"]["outcome"] == "UNSCORABLE_GAP"
    assert result["20_bars"]["outcome"] == "UNSCORABLE_GAP"

    short = score_forecast(forecast(), frame.iloc[:9])
    assert short["10_bars"]["outcome"] == "UNSCORABLE_INCOMPLETE"
    assert short["20_bars"]["outcome"] == "UNSCORABLE_INCOMPLETE"


@pytest.mark.parametrize("bad", [
    {"symbol": "BTCUSDT", "timeframe": "2m", "side": "long", "signal_close_ms": 120_000, "stop": 99},
    {"symbol": "BTCUSDT", "timeframe": "1m", "side": "up", "signal_close_ms": 120_000, "stop": 99},
])
def test_consensus_rejects_unsupported_or_malformed_signals(bad):
    with pytest.raises(ValueError):
        build_consensus([bad], symbol="BTCUSDT", entry_ms=120_000, entry_price=100)


def test_scorer_rejects_invalid_forecast_or_candle_prices():
    with pytest.raises(ValueError):
        score_forecast(dict(forecast(), target=99.5), minute_frame())
    frame = minute_frame()
    frame.loc[0, "h"] = 98.0
    with pytest.raises(ValueError):
        score_forecast(forecast(), frame)
