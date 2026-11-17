from scripts.research.crypto_exhaustive_consensus import (
    RULES, combine_at_bar, enumerate_subsets, epoch_window_rejection,
    evaluate_event, evaluate_event_grid, latest_closed_directions, parse_settlement_ms,
    resample_daily_frame, summarize,
)
import numpy as np
import pandas as pd
import pytest


def test_subset_enumeration_covers_every_nonempty_combination_once():
    subsets = enumerate_subsets()
    assert len(RULES) == 4
    assert len(subsets) == 15
    assert len(set(subsets)) == 15
    assert [sum(len(s) == k for s in subsets) for k in range(1, 5)] == [4, 6, 4, 1]


def test_strict_majority_requires_more_than_half_of_all_members():
    votes = {RULES[0]: {4: ("long", 90)}, RULES[1]: {4: ("long", 92)},
             RULES[2]: {4: ("short", 110)}, RULES[3]: {}}
    assert combine_at_bar(votes, RULES[:2], 4) == ("long", 91.0)
    split_votes = {RULES[0]: {4: ("long", 90)}, RULES[1]: {4: ("short", 110)},
                   RULES[2]: {}, RULES[3]: {}}
    assert combine_at_bar(split_votes, RULES[:3], 4) is None
    assert combine_at_bar(votes, RULES, 4) is None


def test_majority_tie_is_abstention():
    votes = {RULES[0]: {7: ("long", 90)}, RULES[1]: {7: ("short", 110)}}
    assert combine_at_bar(votes, RULES[:2], 7) is None


def _frames(n=40, tf_minutes=1):
    width = tf_minutes * 60_000
    raw_times = np.arange(n * tf_minutes, dtype=np.int64) * 60_000
    raw = pd.DataFrame({"t_open_ms":raw_times, "o":100., "h":100.5, "l":99.5,
                        "c":100., "v":1., "quote_v":100., "trades":1})
    frame = pd.DataFrame({
        "t_open_ms":raw.t_open_ms.iloc[::tf_minutes].to_numpy(),
        "o":np.full(n,100.), "h":np.full(n,100.5), "l":np.full(n,99.5),
        "c":np.full(n,100.), "trades":np.full(n,tf_minutes),
    })
    frame.attrs["tf_minutes"] = tf_minutes
    return frame, raw


def test_epoch_window_requires_complete_fresh_traded_bars():
    frame, raw = _frames()
    assert epoch_window_rejection(frame, raw, 5, 10) is None
    frame.loc[5, "trades"] = 0
    assert epoch_window_rejection(frame, raw, 5, 10) == "signal_bar_no_trades"
    frame.loc[5, "trades"] = 1
    raw.loc[5, "trades"] = 0
    assert epoch_window_rejection(frame, raw, 5, 10) == "signal_close_stale"
    raw.loc[5, "trades"] = 1
    raw.loc[5, "t_open_ms"] = 5 * 60_000 + 1
    assert epoch_window_rejection(frame, raw, 5, 10) == "signal_close_stale"


def test_epoch_window_censors_incomplete_gapped_and_settlement_crossing_events():
    frame, raw = _frames()
    assert epoch_window_rejection(frame, raw, 5, 10, settlement_ms=60*60_000) is None
    assert epoch_window_rejection(frame, raw, 5, 10, settlement_ms=35*60_000) == "exchange_no_new_positions_window"
    skipped_entry = frame.copy()
    skipped_entry.loc[6, "t_open_ms"] = 7 * 60_000
    skipped_entry.attrs["tf_minutes"] = 1
    assert epoch_window_rejection(skipped_entry, raw, 5, 10) == "gap_between_signal_and_entry"
    frame_4h, raw_4h = _frames(tf_minutes=240)
    assert epoch_window_rejection(frame_4h, raw_4h, 5, 20,
                                  settlement_ms=70*60*60_000) == "horizon_crosses_settlement"
    short = frame.iloc[:17].reset_index(drop=True)
    short.attrs["tf_minutes"] = 1
    assert epoch_window_rejection(short, raw.iloc[:17].reset_index(drop=True), 5,
                                  20) == "incomplete_full_horizon"
    gapped = raw.drop(index=8).reset_index(drop=True)
    assert epoch_window_rejection(frame, gapped, 5, 10) == "gap_in_1m_execution_path"


def test_barrier_replay_ignores_zero_trade_rows_and_penalizes_stop_gap():
    frame, raw = _frames()
    raw.loc[7, "l"] = 98.0
    raw.loc[7, "trades"] = 0
    raw.loc[8, "h"] = 102.0
    result = evaluate_event(frame, raw.t_open_ms.to_numpy(), raw.o.to_numpy(),
                            raw.h.to_numpy(), raw.l.to_numpy(), raw.trades.to_numpy(),
                            4, "long", 99.0, 10)
    assert result["reason"] == "target"
    raw.loc[7, "trades"] = 1
    raw.loc[7, "o"] = 98.0
    result = evaluate_event(frame, raw.t_open_ms.to_numpy(), raw.o.to_numpy(),
                            raw.h.to_numpy(), raw.l.to_numpy(), raw.trades.to_numpy(),
                            4, "long", 99.0, 10)
    assert result["reason"] == "stop"
    assert result["net_pct"] == pytest.approx(-2.1)


def test_target_grid_tracks_each_first_touch_without_replaying_the_path():
    frame, raw = _frames()
    raw.loc[5:10, "h"] = 100.0
    raw.loc[5:10, "l"] = 99.5
    raw.loc[7, "h"] = 100.5
    raw.loc[8, "h"] = 101.5
    raw.loc[9, "l"] = 98.0
    outcomes = evaluate_event_grid(
        frame, raw.t_open_ms.to_numpy(), raw.o.to_numpy(), raw.h.to_numpy(),
        raw.l.to_numpy(), raw.trades.to_numpy(), 4, "long", 99.0, 10,
        (0.25, 0.5, 1.0, 2.0),
    )
    assert outcomes[0.25]["reason"] == "target"
    assert outcomes[0.5]["reason"] == "target"
    assert outcomes[1.0]["reason"] == "target"
    assert outcomes[2.0]["reason"] == "stop"
    assert outcomes[0.25]["exit_ms"] == outcomes[0.5]["exit_ms"]
    assert outcomes[1.0]["exit_ms"] > outcomes[0.5]["exit_ms"]


def test_target_grid_keeps_stop_first_for_same_minute_ties():
    frame, raw = _frames()
    raw.loc[5:10, "h"] = 100.0
    raw.loc[5:10, "l"] = 99.5
    raw.loc[7, "h"] = 103.0
    raw.loc[7, "l"] = 98.0
    outcomes = evaluate_event_grid(
        frame, raw.t_open_ms.to_numpy(), raw.o.to_numpy(), raw.h.to_numpy(),
        raw.l.to_numpy(), raw.trades.to_numpy(), 4, "long", 99.0, 10,
        (0.25, 0.5, 1.0, 2.0, 3.0),
    )
    assert all(result["reason"] == "stop" for result in outcomes.values())


def test_short_target_grid_and_gapped_short_stop_use_symmetric_fills():
    frame, raw = _frames()
    raw.loc[5:10, "h"] = 100.5
    raw.loc[5:10, "l"] = 100.0
    raw.loc[7, "l"] = 99.5
    raw.loc[8, "l"] = 98.5
    raw.loc[9, "h"] = 102.0
    outcomes = evaluate_event_grid(
        frame, raw.t_open_ms.to_numpy(), raw.o.to_numpy(), raw.h.to_numpy(),
        raw.l.to_numpy(), raw.trades.to_numpy(), 4, "short", 101.0, 10,
        (0.25, 0.5, 1.0, 2.0),
    )
    assert outcomes[0.25]["reason"] == "target"
    assert outcomes[0.5]["reason"] == "target"
    assert outcomes[1.0]["reason"] == "target"
    assert outcomes[2.0]["reason"] == "stop"

    raw.loc[6, "o"] = 101.2
    raw.loc[6, "h"] = 101.4
    raw.loc[6, "l"] = 100.9
    gapped = evaluate_event_grid(
        frame, raw.t_open_ms.to_numpy(), raw.o.to_numpy(), raw.h.to_numpy(),
        raw.l.to_numpy(), raw.trades.to_numpy(), 4, "short", 101.0, 10,
        (0.25, 0.5),
    )
    assert all(result["reason"] == "stop" for result in gapped.values())
    assert all(result["net_pct"] == pytest.approx(-1.3)
               for result in gapped.values())


def test_two_r_target_grid_matches_independent_single_target_reference():
    rng = np.random.default_rng(20261117)
    frame, raw = _frames()
    raw_times = raw.t_open_ms.to_numpy()
    for side in ("long", "short"):
        sign = 1 if side == "long" else -1
        stop = 99.0 if side == "long" else 101.0
        target = 102.0 if side == "long" else 98.0
        for _ in range(30):
            opens = rng.uniform(98.5, 101.5, len(raw))
            opens[5] = 100.0
            spreads = rng.uniform(0.0, 2.5, len(raw))
            raw_o = opens.copy()
            raw_h = opens + spreads
            raw_l = opens - spreads
            traded = rng.integers(0, 2, len(raw), dtype=np.int64)
            result = evaluate_event_grid(
                frame, raw_times, raw_o, raw_h, raw_l, traded,
                4, side, stop, 10, (2.0,),
            )[2.0]

            entry_i = 5
            entry = float(frame.o.iloc[entry_i])
            begin_ms = int(frame.t_open_ms.iloc[entry_i])
            end_ms = begin_ms + 10 * 60_000
            lo = int(np.searchsorted(raw_times, begin_ms, side="left"))
            hi = int(np.searchsorted(raw_times, end_ms, side="left"))
            reason, exit_price, exit_ms = "timeout", float(frame.c.iloc[14]), int(raw_times[hi-1])
            for j in range(lo, hi):
                if traded[j] <= 0:
                    continue
                hit_stop = raw_l[j] <= stop if side == "long" else raw_h[j] >= stop
                hit_target = raw_h[j] >= target if side == "long" else raw_l[j] <= target
                if hit_stop or hit_target:
                    reason = "stop" if hit_stop else "target"
                    if hit_stop and ((side == "long" and raw_o[j] < stop)
                                     or (side == "short" and raw_o[j] > stop)):
                        exit_price = float(raw_o[j])
                    else:
                        exit_price = stop if hit_stop else target
                    exit_ms = int(raw_times[j])
                    break
            gross = sign * (exit_price / entry - 1.0)
            net = gross - 0.001
            assert result["reason"] == reason
            assert result["exit_ms"] == exit_ms
            assert result["net_pct"] == pytest.approx(100 * net)


def test_settlement_timestamp_parser_requires_utc_and_accepts_epoch_ms():
    assert parse_settlement_ms("2025-09-23T09:00:00Z") == 1758618000000
    assert parse_settlement_ms(1758618000000) == 1758618000000
    try:
        parse_settlement_ms("2025-09-23T09:00:00")
    except ValueError as exc:
        assert "UTC" in str(exc)
    else:
        raise AssertionError("timezone-naive settlement timestamp was accepted")


def test_macro_filter_only_uses_fully_closed_four_hour_bars():
    htf_open = np.array([0, 240*60_000], dtype=np.int64)
    directions = np.array([-1, 1], dtype=np.int64)
    signal_open = np.array([0, 180*60_000, 240*60_000, 420*60_000], dtype=np.int64)
    assert latest_closed_directions(htf_open, directions, 240*60_000,
                                    signal_open, 60*60_000).tolist() == [0, -1, -1, 1]


def test_daily_resampler_keeps_only_complete_utc_days():
    _, raw = _frames(n=2*1440)
    daily = resample_daily_frame(raw)
    assert daily.t_open_ms.tolist() == [0, 86_400_000]
    gapped = raw.drop(index=1500).reset_index(drop=True)
    daily = resample_daily_frame(gapped)
    assert daily.t_open_ms.tolist() == [0]
    off_grid = raw.copy()
    off_grid.loc[0, "t_open_ms"] = 1
    daily = resample_daily_frame(off_grid)
    assert daily.t_open_ms.tolist() == [86_400_000]


def test_summary_separates_target_first_and_deadline_direction_metrics():
    row = summarize([
        {"reason":"target","net_pct":1.0,"net_r":1.0,"symbol":"A",
         "deadline_direction_correct":False},
        {"reason":"timeout","net_pct":0.2,"net_r":0.2,"symbol":"A",
         "deadline_direction_correct":True},
        {"reason":"stop","net_pct":-1.2,"net_r":-1.2,"symbol":"B",
         "deadline_direction_correct":True},
    ])
    assert row["n"] == 3
    assert row["target_first_pct"] == pytest.approx(100 / 3)
    assert row["deadline_direction_accuracy"] == pytest.approx(2 / 3)
    assert row["mean_net_pct"] == pytest.approx(0.0)
    assert row["sum_trade_net_pct"] == pytest.approx(0.0)
    assert row["profit_factor"] == pytest.approx(1.0)
    assert row["timeout_pct"] == pytest.approx(100 / 3)
    assert row["per_symbol"]["A"]["n"] == 2
    assert row["per_symbol"]["B"]["n"] == 1
    assert row["target_first_wilson95_pct"][0] == pytest.approx(6.15, abs=0.1)


def test_empty_summary_keeps_the_same_percent_interval_schema():
    row = summarize([])
    assert row["n"] == 0
    assert row["target_first_wilson95_pct"] == [None, None]
    assert row["deadline_direction_wilson95_pct"] == [None, None]
