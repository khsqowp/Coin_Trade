"""watch fixes: structured last_error + resolution, export retry backoff, KIS rate-limit alert, forward stale-signal-cache regression."""
import datetime as dt
import json
import time

import numpy as np
import pandas as pd
import pytest

from helpers_ext import make_ohlcv
from tp import forward, kisintra, research, watch

UTC = dt.timezone.utc
# Wed 2026-10-28 12:00 KST
NOW = dt.datetime(2026, 10, 28, 3, 0, tzinfo=UTC)


def _loop(monkeypatch, tmp_path, cycles, check=None, write_all=None):
    monkeypatch.setattr(watch, "STATE", tmp_path / "watch_state.json")
    monkeypatch.setattr(watch, "check_all", check or (lambda now: {}))
    if write_all is not None:
        from tp import hermesx
        monkeypatch.setattr(hermesx, "write_all", write_all)
    n = {"i": 0}

    def stop():
        n["i"] += 1
        return n["i"] > cycles
    sent = []
    watch.run_forever(stop=stop, sleep=lambda s: None, send=sent.append)
    return json.loads((tmp_path / "watch_state.json").read_text()), sent


# ------------------------------------------------------------------ 1. structured last_error
def _boom():
    def inner():
        raise ValueError("operands could not be broadcast together with shapes (17536,) (17583,) key=sk-abcdefghijklmnopqrstuv")
    inner()


def test_err_record_structure_and_scrub():
    try:
        _boom()
    except ValueError as e:
        r = watch.err_record(e, "check_all", NOW)
    assert set(r) == {"at", "where", "type", "msg", "tb_tail"}
    assert r["at"] == "2026-10-28T03:00:00Z" and r["where"] == "check_all" and r["type"] == "ValueError"
    assert len(r["msg"]) <= 200 and "sk-abcdefghij" not in r["msg"] and "***" in r["msg"]
    assert 1 <= len(r["tb_tail"]) <= 3 and all(x.count(":") == 2 for x in r["tb_tail"])
    assert any(x.endswith(":inner") for x in r["tb_tail"])


def test_last_error_recorded_then_resolved(monkeypatch, tmp_path):
    calls = {"n": 0}

    def flaky(now):
        calls["n"] += 1
        if calls["n"] == 1:
            _boom()
        return {}
    st, _ = _loop(monkeypatch, tmp_path, 1, check=flaky, write_all=lambda now: {"withheld": {}})
    assert st["last_error"]["where"] == "check_all" and st["last_error"]["type"] == "ValueError"
    assert "sk-abcdefghij" not in json.dumps(st)
    st, _ = _loop(monkeypatch, tmp_path, 1, check=flaky, write_all=lambda now: {"withheld": {}})      # next full cycle succeeds
    assert st["last_error"] is None and st["last_error_resolved_at"]
    assert st["last_error_last"]["where"] == "check_all" and st["last_error_last"]["resolved_at"]


def test_legacy_string_last_error_is_cleared_on_success(monkeypatch, tmp_path):
    (tmp_path / "watch_state.json").write_text(json.dumps({"last_error": "old string error", "open": {}}))
    st, _ = _loop(monkeypatch, tmp_path, 1, write_all=lambda now: {"withheld": {}})
    assert st["last_error"] is None and st["last_error_last"]["msg"] == "old string error"


def test_budget_policy_failure_is_structured(monkeypatch, tmp_path):
    from tp import budget_policy
    monkeypatch.setattr(budget_policy, "propose", lambda now: (_ for _ in ()).throw(RuntimeError("bp down")))
    monkeypatch.setattr(watch, "daily_summary", lambda now: "sum")
    monkeypatch.setattr(watch, "SUMMARY_HOUR_UTC", 0)
    st, sent = _loop(monkeypatch, tmp_path, 1, write_all=lambda now: {"withheld": {}})
    assert sent == ["sum"]
    assert st["last_error"]["where"] == "budget_policy" and st["last_error"]["msg"] == "bp down"


# ------------------------------------------------------------------ 3. export retry
def test_export_backoff_schedule():
    assert [watch.export_backoff(n) for n in (1, 2, 3, 4, 5, 9)] == [300, 600, 1200, 1800, 1800, 1800]


def test_export_failure_retries_with_backoff_and_clears(monkeypatch, tmp_path):
    n = {"calls": 0, "fail": True}

    def wa(now):
        n["calls"] += 1
        if n["fail"]:
            raise OSError("disk full")
        return {"withheld": {}}
    t0 = time.time()
    st, _ = _loop(monkeypatch, tmp_path, 1, write_all=wa)
    assert n["calls"] == 1 and "export_ts" not in st
    assert 299 <= st["export_next_retry"] - t0 <= 305 and st["export_fail_n"] == 1
    assert st["export_error"]["at"] and st["export_error"]["type"] == "OSError" and st["export_error"]["where"] == "export"
    _loop(monkeypatch, tmp_path, 1, write_all=wa)                                           # still inside the 5 min window: no retry
    assert n["calls"] == 1
    s = json.loads((tmp_path / "watch_state.json").read_text())
    s["export_next_retry"] = time.time() - 1                                                # window elapsed
    (tmp_path / "watch_state.json").write_text(json.dumps(s))
    t1 = time.time()
    st, _ = _loop(monkeypatch, tmp_path, 1, write_all=wa)
    assert n["calls"] == 2 and 599 <= st["export_next_retry"] - t1 <= 605 and st["export_fail_n"] == 2
    st["export_next_retry"] = time.time() - 1
    (tmp_path / "watch_state.json").write_text(json.dumps(st))
    n["fail"] = False
    st, _ = _loop(monkeypatch, tmp_path, 1, write_all=wa)
    assert n["calls"] == 3 and st["export_error"] is None and "export_next_retry" not in st and st["export_fail_n"] == 0
    assert time.time() - st["export_ts"] < 10
    _loop(monkeypatch, tmp_path, 1, write_all=wa)                                           # success path unchanged: next export after EXPORT_EVERY_S
    assert n["calls"] == 3


# ------------------------------------------------------------------ 4. KIS rate limit alert
def _kst_status(now, calls, lim):
    return {"heartbeat": now.astimezone(kisintra.KST).isoformat(), "calls_today": calls, "rate_limited_today": lim}


def test_kis_ratelimit_alert_thresholds():
    f = watch.kis_ratelimit_issue
    m = f(_kst_status(NOW, 2374, 395), NOW)
    assert "395" in m and "2374" in m and "16.6%" in m
    assert f(_kst_status(NOW, 199, 100), NOW) is None            # total < 200
    assert f(_kst_status(NOW, 200, 20), NOW) is None             # exactly 10% is not "more than"
    assert f(_kst_status(NOW, 200, 21), NOW) is not None
    assert f(_kst_status(NOW, 1000, 50), NOW) is None
    assert f({"heartbeat": "garbage", "calls_today": 900, "rate_limited_today": 500}, NOW) is None


def test_kis_ratelimit_ignores_stale_or_off_day_counters():
    f = watch.kis_ratelimit_issue
    before_open = dt.datetime(2026, 10, 27, 23, 30, tzinfo=UTC)    # 08:30 KST Wed: counters still hold Tuesday's numbers
    assert f(_kst_status(before_open, 2000, 900), before_open) is None
    yesterday = dict(_kst_status(NOW - dt.timedelta(days=1), 2000, 900))
    assert f(yesterday, NOW) is None
    sat = dt.datetime(2026, 10, 31, 3, 0, tzinfo=UTC)
    assert f(_kst_status(sat, 2000, 900), sat) is None


def test_check_all_emits_one_kis_ratelimit_issue_with_existing_cadence(monkeypatch, tmp_path):
    monkeypatch.setattr(kisintra, "STATUS", tmp_path / "kis.json")
    (tmp_path / "kis.json").write_text(json.dumps(dict(_kst_status(NOW, 2374, 395), state="waiting_market_open")))
    monkeypatch.setattr(watch.shutil, "disk_usage", lambda p: type("U", (), {"free": 90, "total": 100})())
    monkeypatch.setattr(watch.budget, "task_spent", lambda *a, **k: 0.0)
    iss = watch.check_all(NOW)
    assert [k for k in iss if k.startswith("kis_ratelimit")] == ["kis_ratelimit"]
    msgs, st = watch.diff_alerts(iss, {}, 1000)
    assert sum("kis_ratelimit" in m for m in msgs) == 1
    msgs, st = watch.diff_alerts(iss, st, 1100)
    assert not any("kis_ratelimit" in m for m in msgs)
    msgs, st = watch.diff_alerts(iss, st, 1000 + watch.REALERT_S + 1)
    assert sum("kis_ratelimit" in m for m in msgs) == 1


# ------------------------------------------------------------------ 2. forward: stale memoised signal vs grown kline frame
def test_stale_length_series_reproduces_the_original_error():
    short = pd.Series(np.ones(17536), index=make_ohlcv(17536).index)
    with pytest.raises(ValueError, match=r"shapes \(17536,\) \(17583,\)"):
        short * np.ones(17583)


@pytest.fixture()
def grown(tmp_path, monkeypatch):
    short, full = make_ohlcv(17536, drift=0.0001), make_ohlcv(17583, drift=0.0001)
    state = {"df": short}
    monkeypatch.setattr(forward, "REG", tmp_path / "reg.json")
    monkeypatch.setattr(research, "_SIG_CACHE", {})
    monkeypatch.setattr(research, "load_df", lambda sym, tf: state["df"])
    monkeypatch.setattr(research, "fund_arr", lambda sym, d, tf: np.zeros(len(d)))
    monkeypatch.setattr(forward, "llm_rm_series", lambda index, tf: np.ones(len(index)))
    monkeypatch.setattr(research, "retire_active", lambda d, tf, sig, fr: np.ones(len(d)))

    def fake_get_signal(st, side, sym, tf, df=None):         # same memoisation semantics as research.get_signal
        key = (st, side, sym, tf)
        if key not in research._SIG_CACHE:
            research._SIG_CACHE[key] = pd.Series(np.where(np.arange(len(df)) % 200 < 100, 1.0, -1.0), index=df.index)
        return research._SIG_CACHE[key]
    monkeypatch.setattr(research, "get_signal", fake_get_signal)
    return state, full


@pytest.mark.parametrize("name", ["C1_trend_mtf_long_ETH_1h", "C3_trend_mtf_ls_BTC_1h", "C3v_voltarget", "C3r_retire", "C6_llm_rm_on_C3"])
def test_forward_signal_realigned_when_klines_grow(grown, name):
    state, full = grown
    d, sig, _, _ = forward.candidate_signal(name)
    assert len(sig) == len(d) == 17536
    state["df"] = full                                        # tp-news appended 47 bars while tp-watch kept running
    d, sig, _, _ = forward.candidate_signal(name)
    assert len(sig) == len(d) == 17583 and sig.index.equals(d.index)
    reg = {k: d.index[17000].strftime("%Y-%m-%dT%H:%M:%SZ") for k in forward.CANDIDATES}
    r = forward.evaluate(name, reg)
    assert r["status"] != "ERROR" and r["bars"] == 583
