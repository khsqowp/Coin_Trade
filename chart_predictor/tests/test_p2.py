import json
import sqlite3
import sys
import numpy as np
import pandas as pd
import pytest
from chart_predictor import indicators
from chart_predictor.baselines import emit_baseline, expected_stats
from chart_predictor.features import _digest
from chart_predictor.schema import validate_prediction, HORIZON
from chart_predictor.scorer import score_prediction
from chart_predictor.splits import _guard, split_anchors, symbol_split
from chart_predictor.replay import replay
from chart_predictor import cli
from chart_predictor.store import connect_store, connect_trials, append_prediction, cumulative_trial_count
from chart_predictor.stats import wilson, report


def frames(nfuture=20):
    """Make stable 1m history and future fixtures around price 100."""
    n = 30 + nfuture
    t = 1_700_000_000_000 + np.arange(n) * 60_000
    c = np.full(n, 100.0)
    return pd.DataFrame({"t_open_ms": t, "o": c, "h": c + .5, "l": c - .5,
                         "c": c, "v": np.ones(n), "quote_v": c, "trades": np.ones(n, int)})


def prediction(frame, direction="flat", side="none", inv=100):
    """Build a schema-shaped prediction anchored after the 30th row."""
    anchor = int(frame.t_open_ms.iloc[29] + 60_000)
    tf, horizon = "1m", 20
    return {"symbol": "BTCUSDT", "timeframe": tf, "anchor_time": anchor,
        "created_at": "2026-01-01T00:00:00Z", "model": "codex", "prompt_version": "p2",
        "code_sha": "abc", "input_sha256": _digest(frame.iloc[:30]), "direction": direction,
        "confidence": .8, "path": [{"minutes": horizon*k//4, "price": 100} for k in range(1, 5)],
        "target_low": 99, "target_high": 101, "invalidation": inv, "side": side,
        "leverage_suggestion": 2, "rationale": ["fixture"]}


def test_validator_rejects_bad_hash_enum_and_ranges():
    frame = frames()
    pred = prediction(frame)
    assert validate_prediction(pred, frame)
    for key, value in (("input_sha256", "0"*64), ("direction", "sideways"), ("confidence", 2)):
        bad = dict(pred, **{key: value})
        with pytest.raises(ValueError): validate_prediction(bad, frame)
    bad = dict(pred, side="long", invalidation=100)
    with pytest.raises(ValueError): validate_prediction(bad, frame)


@pytest.mark.parametrize("move,expected", [(2, "up"), (-2, "down"), (0, "flat")])
def test_scorer_direction_fixtures(move, expected):
    frame = frames()
    frame.loc[30:, ["c", "o", "h", "l"]] += move
    result = score_prediction(prediction(frame, expected), frame)
    assert result["m1_actual"] == expected and result["m1_hit"]


def test_scorer_target_touch_path_mae_and_same_candle_adverse_first():
    frame = frames()
    frame.loc[39, ["h", "l"]] = [102, 49]
    pred = prediction(frame, "flat", "long", 99)
    result = score_prediction(pred, frame)
    assert result["m2_hit"] and result["m3_mae_usdt"] == 0
    assert result["exit_reason"] == "INVALIDATION" and result["exit_price"] == 99
    assert result["invalidation_hit_time"] == frame.t_open_ms.iloc[39]


def test_scorer_liquidation_fees_and_unscorable():
    frame = frames()
    frame.loc[30, ["h", "l"]] = [100.1, 50.0]
    result = score_prediction(prediction(frame, "flat", "long", 40), frame)
    assert result["exit_reason"] == "LIQUIDATION" and result["net_return"] < 0
    assert result["r_multiple"] is not None
    assert score_prediction(prediction(frame.iloc[:40].copy()), frame.iloc[:40])["status"] == "UNSCORABLE"


def test_append_only_store_trials_and_stats(tmp_path):
    db = connect_store(tmp_path / "pred.sqlite")
    ident = append_prediction(db, {"immutable": 1})
    with pytest.raises(sqlite3.IntegrityError): db.execute("UPDATE predictions SET payload='{}' WHERE id=?", (ident,))
    with pytest.raises(sqlite3.IntegrityError): db.execute("DELETE FROM predictions WHERE id=?", (ident,))
    db.close()
    trials = connect_trials(tmp_path / "trials.sqlite")
    assert cumulative_trial_count(trials) == 0
    trials.execute("INSERT INTO trials(ts) VALUES('now')")
    assert cumulative_trial_count(trials) == 1
    trials.close()
    assert wilson(50, 100) == pytest.approx({"low": .4038, "high": .5962}, abs=.0001)


def test_baselines_and_splits_deterministic():
    frame = frames()
    for name in ("momentum", "random", "flat"):
        pred = emit_baseline(name, frame.iloc[:30], "BTCUSDT", "1m", int(frame.t_open_ms.iloc[29]+60_000), seed=7)
        assert pred["model"] == f"baseline_{name}" and len(pred["path"]) == 4
        assert validate_prediction(pred, frame.iloc[:30])
    anchors = pd.DataFrame({"anchor_time_ms": np.arange(100)})
    assert split_anchors(anchors, "dev").anchor_time_ms.tolist() == list(range(60))
    assert symbol_split("BTCUSDT") == symbol_split("BTCUSDT")
    assert expected_stats()["random"]["expected_accuracy_if_labels_balanced"] == pytest.approx(1/3)


def test_sealed_access_logs_before_raising(tmp_path):
    reg, trials = tmp_path / "registry.json", tmp_path / "trials.sqlite"
    reg.write_text(json.dumps({"freeze_timestamp": "2026-01-01T00:00:00Z"}))
    anchors = pd.DataFrame({"anchor_time_ms": [1_800_000_000_000]})
    with pytest.raises(PermissionError): _guard(anchors, "BTCUSDT", "1m", reg, trials)
    db = connect_trials(trials)
    assert cumulative_trial_count(db) == 1
    db.close()


def test_batch_feature_prefix_is_future_mutation_invariant():
    frame = frames(5)
    prefix = frame.iloc[:30]
    original = _digest(prefix)
    changed = frame.copy()
    changed.loc[30:, ["o", "h", "l", "c", "v"]] *= 1000
    assert _digest(changed.iloc[:30]) == original
    assert HORIZON["1m"] == 20


def test_trade_fees_and_stats_confidence_coverage():
    frame = frames()
    frame.loc[30:, "c"] = np.linspace(100, 101, 20)
    pred = prediction(frame, "up", "long", 90)
    pred["path"] = [{"minutes": m, "price": 101} for m in (5, 10, 15, 20)]
    charged = score_prediction(pred, frame)
    free = score_prediction(pred, frame, taker_fee=0, slippage=0)
    assert free["net_return"] > charged["net_return"]
    rows = [{"status": "SCORED", "m1_hit": True, "confidence": .9, "symbol": "A",
             "timeframe": "1m", "anchor_time": "2026-01-01T00:00:00Z", "model": "baseline_flat"},
            {"status": "UNSCORABLE", "m1_hit": False, "confidence": .2, "symbol": "B",
             "timeframe": "5m", "anchor_time": "2026-01-01T00:00:00Z", "model": "codex"}]
    result = report(rows)
    assert result["m4"]["0.9"]["coverage"] == .5
    assert result["clustered_by_anchor_day"]["2026-01-01"]["n"] == 1
    assert "baseline_flat" in result["baselines"]


def test_replay_batch_has_no_future_and_anchors_do_not_overlap(tmp_path):
    frame = frames(70)
    dbpath = tmp_path / "candles.sqlite"
    db = sqlite3.connect(dbpath)
    frame.insert(0, "symbol", "BTCUSDT")
    frame.to_sql("candles", db, index=False)
    db.close()
    registry = tmp_path / "sealed.json"
    registry.write_text(json.dumps({"freeze_timestamp": "2030-01-01T00:00:00Z"}))
    result = replay("dev", ["BTCUSDT"], "1m", dbpath, tmp_path / "batches", registry)
    manifest = json.loads((tmp_path / "batches" / "manifest_dev_1m.json").read_text())
    assert result["count"] > 0 and manifest
    times = [item["anchor_time_ms"] for item in manifest]
    assert all(b-a >= 20*60_000 for a, b in zip(times, times[1:]))
    for item in manifest:
        payload = json.loads((tmp_path / "batches" / item["file"]).read_text())
        assert "candles" not in payload and "outcomes" not in payload and "realized" not in payload
        assert payload["features"]["input_sha256"] == item["input_sha256"]


def test_cli_ingest_score_report_roundtrip(tmp_path, monkeypatch, capsys):
    frame = frames()
    data_path = tmp_path / "data.sqlite"
    db = sqlite3.connect(data_path)
    frame.assign(symbol="BTCUSDT").to_sql("candles", db, index=False)
    db.close()
    pred = prediction(frame)
    pred_path = tmp_path / "prediction.json"
    pred_path.write_text(json.dumps(pred))
    args = ["ingest", "--file", str(pred_path), "--db", str(tmp_path / "pred.sqlite"),
            "--trials-db", str(tmp_path / "trials.sqlite"), "--data-db", str(data_path)]
    monkeypatch.setattr(sys, "argv", ["chart_predictor.cli", *args])
    cli.main()
    assert json.loads(capsys.readouterr().out)["ingested"] == 1
    args = ["score", "--db", str(tmp_path / "pred.sqlite"), "--data-db", str(data_path)]
    monkeypatch.setattr(sys, "argv", ["chart_predictor.cli", *args])
    cli.main()
    assert json.loads(capsys.readouterr().out)["scored"] == 1
    monkeypatch.setattr(sys, "argv", ["chart_predictor.cli", "report", "--db", str(tmp_path / "pred.sqlite")])
    cli.main()
    report_data = json.loads(capsys.readouterr().out)
    assert report_data["overall"]["n"] == 1 and "success" not in report_data


@pytest.mark.parametrize("side,inv,high,low,expected", [
    ("long", 99, 101, 49, ("INVALIDATION", 99)),
    ("short", 101, 151, 99, ("INVALIDATION", 101)),
])
def test_both_stops_touch_nearer_stop_wins(side, inv, high, low, expected):
    frame = frames()
    frame.loc[30, ["h", "l"]] = [high, low]
    pred = prediction(frame, "flat", side, inv)
    result = score_prediction(pred, frame, entry_delay_candles=0)
    assert (result["exit_reason"], result["exit_price"]) == expected


@pytest.mark.parametrize("side,inv,open_price,high,low", [
    ("long", 99, 98, 99, 97),
    ("short", 101, 102, 103, 101),
])
def test_gap_through_invalidation_fills_at_open(side, inv, open_price, high, low):
    frame = frames()
    frame.loc[30, ["o", "h", "l"]] = [open_price, high, low]
    result = score_prediction(prediction(frame, "flat", side, inv), frame, entry_delay_candles=0)
    assert result["exit_reason"] == "INVALIDATION"
    assert result["exit_price"] == open_price
    assert result["net_return"] == pytest.approx(-.04 - 2 * (.0005 + .0002) * 2)


def test_entry_delay_changes_fill_price_and_stop_scan_start():
    frame = frames()
    frame.loc[30, ["o", "l"]] = [101, 98]
    frame.loc[31, ["o", "h", "l"]] = [102, 103, 100]
    pred = prediction(frame, "flat", "long", 99)
    legacy = score_prediction(pred, frame, entry_delay_candles=0)
    default = score_prediction(pred, frame)
    delayed = score_prediction(pred, frame, entry_delay_candles=2)
    assert legacy["entry_price"] == 100 and legacy["exit_reason"] == "INVALIDATION"
    assert default["entry_price"] == 101 and default["exit_reason"] == "INVALIDATION"
    assert delayed["entry_price"] == 102 and delayed["exit_reason"] == "HORIZON"
    expected_net = ((99 / 101) - 1) * 2 - 2 * (.0005 + .0002) * 2
    expected_risk = abs(101 - 99) / 101 * 2
    assert default["net_return"] == pytest.approx(expected_net)
    assert default["r_multiple"] == pytest.approx(expected_net / expected_risk)


@pytest.mark.parametrize("leverage", [2, 5, 10, 125])
def test_liquidation_distance_uses_leverage_and_actual_entry(leverage):
    frame = frames()
    entry, fraction = 100.0, 1 / leverage - .005
    liquidation = entry * (1 - fraction)
    frame.loc[30, ["o", "h", "l"]] = [entry, entry + .1, liquidation - .01]
    pred = prediction(frame, "flat", "long", 40)
    pred["leverage_suggestion"] = leverage
    result = score_prediction(pred, frame)
    assert result["exit_reason"] == "LIQUIDATION"
    assert result["exit_price"] == pytest.approx(liquidation)
    assert result["entry_price"] == entry


def test_short_liquidation_gap_and_entry_price_mirror():
    frame = frames()
    frame.loc[30, ["o", "h", "l"]] = [101, 101.5, 100.9]
    frame.loc[31, ["o", "h", "l"]] = [103, 160, 102.5]
    pred = prediction(frame, "flat", "short", 200)
    delayed = score_prediction(pred, frame)
    assert delayed["entry_price"] == 101 and delayed["exit_reason"] == "LIQUIDATION"
    assert delayed["exit_price"] == pytest.approx(101 * (1 + .5 - .005))
    expected_net = -(delayed["exit_price"] / 101 - 1) * 2 - 2 * (.0005 + .0002) * 2
    assert delayed["net_return"] == pytest.approx(expected_net)
    gap = frames()
    gap.loc[30, ["o", "h", "l"]] = [102, 103, 101.5]
    gap_result = score_prediction(prediction(gap, "flat", "short", 101), gap,
                                  entry_delay_candles=0)
    assert gap_result["exit_reason"] == "INVALIDATION" and gap_result["exit_price"] == 102
