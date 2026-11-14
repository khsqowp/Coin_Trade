import json
import os
import sqlite3

import numpy as np
import pandas as pd
import pytest

from chart_predictor import cli
from chart_predictor.features import _digest
from chart_predictor.p3a import ingest_dir, make_agent_tasks, run_baselines, _data_fingerprint, _run_identity, _readonly, _PrefixDigester
from chart_predictor.baselines import emit_baseline
from chart_predictor.scorer import score_prediction
from chart_predictor.splits import symbol_split
from chart_predictor.schema import validate_prediction


def candle_db(path, count=2400, future_scale=1.0):
    """Create a deterministic candle fixture without touching package data."""
    symbol = next(f"T{i}USDT" for i in range(100) if symbol_split(f"T{i}USDT") == "dev")
    t = 1_700_000_000_000 + np.arange(count) * 60_000
    close = 100 + np.arange(count) * .05
    close[-100:] *= future_scale
    db = sqlite3.connect(path)
    pd.DataFrame({"symbol": symbol, "t_open_ms": t, "o": close, "h": close + .1,
                  "l": close - .1, "c": close, "v": 1., "quote_v": close,
                  "trades": 1}).to_sql("candles", db, index=False)
    db.close()
    return symbol


def task_payload(root):
    """Collect task file bytes as parsed JSON for deterministic comparisons."""
    path = next(root.rglob("task_*.json"))
    return json.loads(path.read_text())


def test_baseline_report_numbers_and_seed_are_deterministic(tmp_path):
    db_path = tmp_path / "candles.sqlite"
    candle_db(db_path)
    kwargs = {"split": "dev", "per_cell": 2, "seed": 41, "symbols": 1,
              "data_db": db_path, "trials_db": tmp_path / "trials.sqlite"}
    first = run_baselines(**kwargs)
    first_report = json.loads(pd.io.common.file_exists(first["report"]) and open(first["report"]).read())
    second = run_baselines(**kwargs)
    second_report = json.loads(open(second["report"]).read())
    assert first_report == second_report
    result = first_report["timeframes"]["1m"]["baseline_flat"]
    assert result["n"] == 2 and result["coverage"] == 1 and result["trade_coverage"] == 0
    assert result["m1_accuracy"] is not None and "anchor_day_clusters" in result
    assert first_report["n_predictions"] == first_report["n_cells"] * 2 * 5
    assert first_report["data_fingerprint"]["sha256"] == first_report["data_fingerprint"]["sha256"]
    assert first_report["data_fingerprint"]["symbols"]
    assert "Data fingerprint" in open(first["markdown"]).read()
    assert first_report["baseline_count"] == 5 and first["reused"] is False and second["reused"] is True
    assert (tmp_path / "pred_baselines.sqlite").exists() is False
    assert (tmp_path / "runs" / first["run_id"] / "pred.sqlite").exists()
    trials = sqlite3.connect(tmp_path / "trials.sqlite")
    hypothesis, fingerprint = trials.execute("SELECT hypothesis,data_fingerprint FROM trials ORDER BY trial_id DESC LIMIT 1").fetchone()
    assert "pre-LLM label definition change" in hypothesis and "sqrt(H_candles)" in hypothesis
    assert fingerprint == first_report["data_fingerprint"]["sha256"]
    trials.close()
    assert first_report["timeframes"]["1m"]["baseline_always_up"]["binary_accuracy"] is not None
    assert first_report["timeframes"]["1m"]["baseline_always_down"]["binary_accuracy"] is not None


def test_fingerprint_changes_with_rows_or_symbol_range_and_force_is_fresh(tmp_path):
    db_path = tmp_path / "candles.sqlite"
    symbol = candle_db(db_path)
    def fingerprint():
        db = _readonly(db_path)
        try:
            return _data_fingerprint(db, db_path)
        finally:
            db.close()
    initial = fingerprint()
    same = fingerprint()
    assert initial["sha256"] == same["sha256"]
    os.utime(db_path, ns=(initial["file_mtime_ns"], initial["file_mtime_ns"] + 1_000_000))
    touched = fingerprint()
    assert touched["sha256"] == initial["sha256"]
    assert touched["file_mtime_ns"] != initial["file_mtime_ns"]
    run_id, _ = _run_identity("dev", 1, 1, 1, .25, initial)
    db = sqlite3.connect(db_path)
    row = db.execute("SELECT * FROM candles WHERE symbol=? ORDER BY t_open_ms DESC LIMIT 1", (symbol,)).fetchone()
    db.execute("INSERT INTO candles VALUES(?,?,?,?,?,?,?,?,?)", (row[0], row[1] + 60_000, *row[2:]))
    db.commit()
    db.close()
    after_extra = fingerprint()
    assert after_extra["sha256"] != initial["sha256"]
    extra_id, _ = _run_identity("dev", 1, 1, 1, .25, after_extra)
    assert extra_id != run_id
    db = sqlite3.connect(db_path)
    db.execute("UPDATE candles SET t_open_ms=t_open_ms+60000 WHERE symbol=? AND t_open_ms=(SELECT MIN(t_open_ms) FROM candles WHERE symbol=?)",
               (symbol, symbol))
    db.commit()
    db.close()
    ranged = fingerprint()
    assert ranged["sha256"] != after_extra["sha256"]
    range_id, _ = _run_identity("dev", 1, 1, 1, .25, ranged)
    assert range_id != extra_id

    # Force behavior uses a tiny but eligible run and preserves both directories.
    small_db = tmp_path / "small.sqlite"
    small_symbol = candle_db(small_db, count=2400)
    kwargs = {"split": "dev", "per_cell": 1, "symbols": 1, "data_db": small_db,
              "trials_db": tmp_path / "trials.sqlite"}
    normal = run_baselines(**kwargs)
    reused = run_baselines(**kwargs)
    assert reused["reused"] is True and reused["run_id"] == normal["run_id"]
    db = sqlite3.connect(small_db)
    last = db.execute("SELECT * FROM candles WHERE symbol=? ORDER BY t_open_ms DESC LIMIT 1", (small_symbol,)).fetchone()
    db.execute("INSERT INTO candles VALUES(?,?,?,?,?,?,?,?,?)", (last[0], last[1] + 60_000, *last[2:]))
    db.commit()
    db.close()
    changed = run_baselines(**kwargs)
    assert changed["run_id"] != normal["run_id"] and changed["reused"] is False
    forced = run_baselines(**kwargs, force=True)
    assert forced["run_id"] != changed["run_id"] and forced["run_id"].endswith("_force_001")
    assert (tmp_path / "runs" / normal["run_id"] / "report.json").exists()
    assert (tmp_path / "runs" / changed["run_id"] / "report.json").exists()
    assert (tmp_path / "runs" / forced["run_id"] / "report.json").exists()


def test_incremental_prefix_digest_matches_feature_digest():
    values = np.arange(80)
    frame = pd.DataFrame({"t_open_ms": 1_700_000_000_000 + values * 60_000,
        "o": 10.1234567890123 + values, "h": 11.1234567890123 + values,
        "l": 9.1234567890123 + values, "c": 10.5 + values, "v": 1.25 + values,
        "quote_v": 10.75 + values, "trades": values + 1})
    digester = _PrefixDigester(frame)
    for end in (15, 27, 80):
        assert digester.digest(frame.iloc[:end]) == _digest(frame.iloc[:end])


def test_flat_band_scales_with_sqrt_horizon_and_always_models_validate():
    n = 50
    t = 1_700_000_000_000 + np.arange(n) * 60_000
    close = np.full(n, 100.)
    close[30:] = 100.15
    frame = pd.DataFrame({"t_open_ms": t, "o": close, "h": close + .1,
                          "l": close - .1, "c": close, "v": 1., "quote_v": close,
                          "trades": 1})
    pred = emit_baseline("flat", frame.iloc[:30], "BTCUSDT", "1m", int(t[29] + 60_000))
    score = score_prediction(pred, frame)
    assert score["flat_band"] == pytest.approx(.25 * .2 * np.sqrt(20))
    assert score["m1_actual"] == "flat"
    for name, direction, side in (("always_up", "up", "long"), ("always_down", "down", "short")):
        item = emit_baseline(name, frame.iloc[:30], "BTCUSDT", "1m", int(t[29] + 60_000))
        assert item["direction"] == direction and item["side"] == side
        assert validate_prediction(item, frame.iloc[:30])


def test_agent_tasks_do_not_change_when_future_candles_mutate(tmp_path, monkeypatch, capsys):
    source = tmp_path / "original.sqlite"
    changed = tmp_path / "changed.sqlite"
    candle_db(source, count=2600)
    candle_db(changed, count=2600, future_scale=4)
    one = make_agent_tasks("dev", 1, 7, 100, 1, source, tmp_path / "tasks_a")
    two = make_agent_tasks("dev", 1, 7, 100, 1, changed, tmp_path / "tasks_b")
    items_a, items_b = task_payload(tmp_path / "tasks_a"), task_payload(tmp_path / "tasks_b")
    assert [(x["symbol"], x["timeframe"], x["anchor_time"], x["input_sha256"], x["features"])
            for x in items_a] == [(x["symbol"], x["timeframe"], x["anchor_time"], x["input_sha256"], x["features"])
                                  for x in items_b]
    assert all(not ({"outcomes", "realized", "future", "split"} & set(item)) for item in items_a)
    assert one["tasks"] == two["tasks"]
    monkeypatch.setattr("sys.argv", ["cli", "make-agent-tasks", "--split", "dev", "--per-cell", "1", "--seed", "7",
                                     "--batch-size", "100", "--symbols", "1", "--data-db", str(source),
                                     "--tasks-dir", str(tmp_path / "cli_tasks")])
    cli.main()
    assert json.loads(capsys.readouterr().out)["tasks"] > 0


def test_ingest_dir_reports_each_invalid_file(tmp_path, monkeypatch, capsys):
    db_path = tmp_path / "candles.sqlite"
    candle_db(db_path)
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "task_0001.json").write_text("[]")
    (run_dir / "out_claude_task_0001.json").write_text("not-json")
    (run_dir / "out_claude_task_0002.json").write_text("{}")
    result = ingest_dir(run_dir, "claude", db_path, tmp_path / "pred.sqlite")
    assert result["ingested"] == 0 and result["rejected_files"] == 2
    assert "JSONDecodeError" in result["files"][0]["reason"]
    assert "JSON array" in result["files"][1]["reason"]
    monkeypatch.setattr("sys.argv", ["cli", "ingest-dir", "--dir", str(run_dir), "--model", "claude",
                                     "--data-db", str(db_path), "--db", str(tmp_path / "cli_pred.sqlite")])
    cli.main()
    assert json.loads(capsys.readouterr().out)["rejected_files"] == 2


def test_cli_baselines_command_emits_json(tmp_path, monkeypatch, capsys):
    db_path = tmp_path / "candles.sqlite"
    candle_db(db_path)
    monkeypatch.setattr("sys.argv", ["cli", "baselines", "--split", "dev", "--per-cell", "1",
                                     "--symbols", "1", "--seed", "4", "--data-db", str(db_path),
                                     "--trials-db", str(tmp_path / "trials.sqlite"), "--force"])
    cli.main()
    result = json.loads(capsys.readouterr().out)
    assert result["n_predictions"] > 0 and "_force_001" in result["run_id"]


def test_non_minute_horizon_uses_minutes_not_bar_count():
    n = 60
    t = 1_700_000_000_000 + np.arange(n) * 300_000
    close = np.full(n, 100.0)
    frame = pd.DataFrame({"t_open_ms": t, "o": close, "h": close + .2,
                          "l": close - .2, "c": close, "v": 1., "quote_v": close,
                          "trades": 1})
    pred = emit_baseline("flat", frame.iloc[:40], "BTCUSDT", "5m", int(t[39] + 300_000))
    assert score_prediction(pred, frame)["status"] == "SCORED"
    assert score_prediction(pred, frame.iloc[:59])["status"] == "UNSCORABLE"
