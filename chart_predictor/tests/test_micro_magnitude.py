import hashlib
import json
import sqlite3

from chart_predictor import micro_magnitude as mm


def test_symbol_scan_is_chunk_invariant_and_excludes_invalid_three_bar_windows(tmp_path, monkeypatch):
    db = tmp_path / "candles.sqlite"
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE candles (symbol TEXT, open_ms INTEGER, open REAL, high REAL, "
        "low REAL, close REAL, volume REAL, PRIMARY KEY(symbol,open_ms))"
    )
    price = 100.0
    rows = []
    for index in range(30):
        open_price = price
        price *= 1.001 if index % 2 else 0.999
        close_price = price
        high = max(open_price, close_price) * 1.001
        low = min(open_price, close_price) * 0.999
        if index == 15:
            high = low / 2  # invalid OHLC; adjacent prediction triples are ineligible
        rows.append(("TEST", index * mm.MINUTE_MS, open_price, high, low, close_price, 1.0))
    conn.executemany("INSERT INTO candles VALUES(?,?,?,?,?,?,?)", rows)
    conn.commit()
    conn.close()

    monkeypatch.setattr(mm, "TRAIN_START", 0)
    monkeypatch.setattr(mm, "TRAIN_END", 10 * mm.MINUTE_MS)
    monkeypatch.setattr(mm, "EVAL_START", 10 * mm.MINUTE_MS)
    monkeypatch.setattr(mm, "EVAL_END", mm.EVAL_START + 2 * 86_400_000)
    monkeypatch.setattr(mm, "MIN_TRAIN", 2)
    monkeypatch.setattr(mm, "MIN_EVAL", 2)
    monkeypatch.setattr(mm, "CHUNK_ROWS", 4)

    results = []
    for chunk_rows in (1, 4, 7):
        monkeypatch.setattr(mm, "CHUNK_ROWS", chunk_rows)
        conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        results.append(mm._analyze_symbol(conn, "TEST"))
        conn.close()

    for result in results:
        assert result["eligible"] is True
        assert result["train_returns"] == 8
        assert result["eval_forecasts"] == 16
        assert result["invalid_rows"] == 1
        assert result["offgrid_rows"] == 0
        assert result["adjacency_gaps"] == 0
    assert [result["daily_loss_sums"] for result in results].count(
        results[0]["daily_loss_sums"]
    ) == len(results)


def test_run_persists_outcome_blind_preflight_before_scoring(tmp_path, monkeypatch):
    db = tmp_path / "candles.sqlite"
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE candles (symbol TEXT, open_ms INTEGER, open REAL, high REAL, "
        "low REAL, close REAL, volume REAL, PRIMARY KEY(symbol,open_ms))"
    )
    rows = []
    for symbol_index in range(20):
        price = 100.0 + symbol_index
        for index in range(40):
            open_price = price
            price *= 1.001 if index % 2 else 0.999
            close_price = price
            rows.append((
                f"S{symbol_index:02d}", index * mm.MINUTE_MS, open_price,
                max(open_price, close_price) * 1.001,
                min(open_price, close_price) * 0.999,
                close_price, 1.0,
            ))
    conn.executemany("INSERT INTO candles VALUES(?,?,?,?,?,?,?)", rows)
    conn.commit()
    conn.close()

    monkeypatch.setattr(mm, "TRAIN_START", 0)
    monkeypatch.setattr(mm, "TRAIN_END", 10 * mm.MINUTE_MS)
    monkeypatch.setattr(mm, "EVAL_START", 10 * mm.MINUTE_MS)
    monkeypatch.setattr(mm, "EVAL_END", 14 * mm.MINUTE_MS)
    monkeypatch.setattr(mm, "MIN_TRAIN", 2)
    monkeypatch.setattr(mm, "MIN_EVAL", 2)
    monkeypatch.setattr(mm, "BOOTSTRAP_REPS", 20)
    monkeypatch.setattr(mm, "CHUNK_ROWS", 17)
    monkeypatch.setattr(mm, "EXPECTED_SHA256", hashlib.sha256(db.read_bytes()).hexdigest())

    output = tmp_path / "result.json"
    preflight_path = output.with_name(output.name + ".state") / "preflight.json"
    original = mm._analyze_symbol
    scoring_started = False

    def assert_preflight_precedes_scoring(conn, symbol, **kwargs):
        nonlocal scoring_started
        if kwargs.get("score", True):
            assert preflight_path.is_file()
            assert json.loads(preflight_path.read_text())["outcome_scoring_started"] is False
            scoring_started = True
        return original(conn, symbol, **kwargs)

    monkeypatch.setattr(mm, "_analyze_symbol", assert_preflight_precedes_scoring)
    report = mm.run(db, output, expected_sha256=mm.EXPECTED_SHA256)

    assert scoring_started
    assert len(report["symbols"]) == 20
    assert report["symbols"][0]["eval_forecasts"] == 2
    assert preflight_path.is_file()
    assert output.is_file()
    assert (output.with_name(output.name + ".state") / "score_symbols").is_dir()


def test_hash_can_be_interrupted_between_bounded_chunks(tmp_path):
    source = tmp_path / "large.bin"
    source.write_bytes(b"x" * (mm.CHUNK_ROWS + 1))
    progress = []

    try:
        mm.sha256_file(source, progress=progress.append,
                       stop_requested=lambda: bool(progress))
    except mm.RunInterrupted:
        pass
    else:
        raise AssertionError("hash should stop after its first bounded chunk")

    assert progress == [source.stat().st_size]


def test_interrupted_run_resumes_completed_symbol_checkpoints(tmp_path, monkeypatch):
    db = tmp_path / "candles.sqlite"
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE candles (symbol TEXT, open_ms INTEGER, open REAL, high REAL, "
        "low REAL, close REAL, volume REAL, PRIMARY KEY(symbol,open_ms))"
    )
    rows = []
    for symbol_index in range(20):
        price = 100.0 + symbol_index
        for index in range(40):
            open_price = price
            price *= 1.001 if index % 2 else 0.999
            close_price = price
            rows.append((
                f"S{symbol_index:02d}", index * mm.MINUTE_MS, open_price,
                max(open_price, close_price) * 1.001,
                min(open_price, close_price) * 0.999,
                close_price, 1.0,
            ))
    conn.executemany("INSERT INTO candles VALUES(?,?,?,?,?,?,?)", rows)
    conn.commit()
    conn.close()

    monkeypatch.setattr(mm, "TRAIN_START", 0)
    monkeypatch.setattr(mm, "TRAIN_END", 10 * mm.MINUTE_MS)
    monkeypatch.setattr(mm, "EVAL_START", 10 * mm.MINUTE_MS)
    monkeypatch.setattr(mm, "EVAL_END", 14 * mm.MINUTE_MS)
    monkeypatch.setattr(mm, "MIN_TRAIN", 2)
    monkeypatch.setattr(mm, "MIN_EVAL", 2)
    monkeypatch.setattr(mm, "BOOTSTRAP_REPS", 20)
    monkeypatch.setattr(mm, "CHUNK_ROWS", 17)
    expected_sha = hashlib.sha256(db.read_bytes()).hexdigest()
    output = tmp_path / "resumable.json"
    original = mm._analyze_symbol
    stop = {"requested": False}
    first_score_calls = []

    def interrupt_after_one_score(conn, symbol, **kwargs):
        result = original(conn, symbol, **kwargs)
        if kwargs.get("score", True):
            first_score_calls.append(symbol)
            if len(first_score_calls) == 1:
                stop["requested"] = True
        return result

    monkeypatch.setattr(mm, "_analyze_symbol", interrupt_after_one_score)
    try:
        mm.run(db, output, expected_sha256=expected_sha,
               stop_requested=lambda: stop["requested"])
    except mm.RunInterrupted:
        pass
    else:
        raise AssertionError("first run should stop after the first completed score checkpoint")

    assert first_score_calls == ["S00"]
    assert not output.exists()
    assert (output.with_name(output.name + ".state") / "status.json").is_file()

    stop["requested"] = False
    resumed_score_calls = []

    def track_resume_scoring(conn, symbol, **kwargs):
        if kwargs.get("score", True):
            resumed_score_calls.append(symbol)
        return original(conn, symbol, **kwargs)

    monkeypatch.setattr(mm, "_analyze_symbol", track_resume_scoring)
    report = mm.run(db, output, expected_sha256=expected_sha,
                    stop_requested=lambda: stop["requested"])

    assert report["eligible_symbols"] == 20
    assert "S00" not in resumed_score_calls
    assert output.is_file()
