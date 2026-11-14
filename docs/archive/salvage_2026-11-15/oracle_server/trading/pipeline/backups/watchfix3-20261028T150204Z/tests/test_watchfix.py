"""watch fixes: structured last_error + resolution, export retry/failing, KIS pacing alert (stale guard, hysteresis, hold), watchdog self-health,
atomic state write, pending alerts, and forward stale-signal-cache regressions through the REAL research.get_signal path."""
import datetime as dt
import json
import os
import time

import numpy as np
import pandas as pd
import pytest

from helpers_ext import make_ohlcv
from tp import forward, kisintra, research, watch

UTC = dt.timezone.utc
NOW = dt.datetime(2026, 10, 28, 3, 0, tzinfo=UTC)          # Wed 12:00 KST
KST = kisintra.KST


def _loop(monkeypatch, tmp_path, cycles, check=None, write_all=None, send=None, summary_hour=25):
    monkeypatch.setattr(watch, "STATE", tmp_path / "watch_state.json")
    monkeypatch.setattr(watch, "SUMMARY_HOUR_UTC", summary_hour)      # 25 = never reached: the daily summary / budget_policy stage stays out of unrelated tests
    monkeypatch.setattr(watch, "check_all", check or (lambda now, wst=None: {}))
    if write_all is not None:
        from tp import hermesx
        monkeypatch.setattr(hermesx, "write_all", write_all)
    n = {"i": 0}

    def stop():
        n["i"] += 1
        return n["i"] > cycles
    sent = []
    watch.run_forever(stop=stop, sleep=lambda s: None, send=send or sent.append)
    return json.loads((tmp_path / "watch_state.json").read_text()), sent


def _state(tmp_path, **kw):
    (tmp_path / "watch_state.json").write_text(json.dumps(kw))


OK_EXPORT = lambda now: {"withheld": {}}       # noqa: E731


# ------------------------------------------------------------------ 1. structured last_error
def _boom():
    def inner():
        raise ValueError("operands could not be broadcast together with shapes (17536,) (17583,) key=sk-abcdefghijklmnopqrstuv")
    inner()


def test_err_record_structure_and_scrub():
    try:
        _boom()
    except ValueError as e:
        r = watch.err_record(e, "check_all")
    assert set(r) == {"at", "where", "type", "msg", "tb_tail"}
    assert r["at"].endswith("Z") and abs(dt.datetime.strptime(r["at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC) - dt.datetime.now(UTC)).seconds < 5
    assert r["where"] == "check_all" and r["type"] == "ValueError"
    assert len(r["msg"]) <= 200 and "sk-abcdefghij" not in r["msg"] and "***" in r["msg"]
    assert 1 <= len(r["tb_tail"]) <= 3 and all(x.count(":") == 2 for x in r["tb_tail"])      # fallback: no /tp/ frame in this traceback


def test_err_record_prefers_pipeline_frames():
    try:
        watch.export_backoff("x")                # TypeError raised inside tp/watch.py, called from the test file
    except TypeError as e:
        r = watch.err_record(e, "export")
    assert len(r["tb_tail"]) == 1 and r["tb_tail"][0].startswith("watch.py:") and r["tb_tail"][0].endswith(":export_backoff")


def test_err_record_survives_unprintable_exception():
    class Bad(Exception):
        def __str__(self):
            raise RuntimeError("no str")
    try:
        raise Bad()
    except Bad as e:
        r = watch.err_record(e, "x")
    assert r["msg"] == "error record unavailable" and r["tb_tail"] == [] and r["at"]


def test_last_error_recorded_then_resolved(monkeypatch, tmp_path):
    calls = {"n": 0}

    def flaky(now, wst=None):
        calls["n"] += 1
        if calls["n"] == 1:
            _boom()
        return {}
    st, _ = _loop(monkeypatch, tmp_path, 1, check=flaky, write_all=OK_EXPORT)
    assert st["last_error"]["where"] == "check_all" and st["last_error"]["type"] == "ValueError" and st["fail_streak"] == 1
    assert "sk-abcdefghij" not in json.dumps(st)
    st, _ = _loop(monkeypatch, tmp_path, 1, check=flaky, write_all=OK_EXPORT)
    assert st["last_error"] is None and st["last_error_resolved_at"] and st["fail_streak"] == 0
    assert st["last_error_last"]["where"] == "check_all" and st["last_error_last"]["resolved_at"]


def test_legacy_string_last_error_is_cleared_on_success(monkeypatch, tmp_path):
    _state(tmp_path, last_error="old string error", open={})
    st, _ = _loop(monkeypatch, tmp_path, 1, write_all=OK_EXPORT)
    assert st["last_error"] is None and st["last_error_last"]["msg"] == "old string error"


def test_budget_policy_error_survives_until_next_daily_attempt(monkeypatch, tmp_path):
    from tp import budget_policy
    res = {"fail": True}

    def propose(now):
        if res["fail"]:
            raise RuntimeError("bp down")
        return None, {}
    monkeypatch.setattr(budget_policy, "propose", propose)
    monkeypatch.setattr(watch, "daily_summary", lambda now: "sum")
    st, _ = _loop(monkeypatch, tmp_path, 1, write_all=OK_EXPORT, summary_hour=0)               # daily attempt fails
    assert st["last_error"]["where"] == "budget_policy" and st["last_error"]["msg"] == "bp down"
    st, _ = _loop(monkeypatch, tmp_path, 3, write_all=OK_EXPORT, summary_hour=0)               # same day: no attempt -> error stays
    assert st["last_error"]["where"] == "budget_policy" and st["fail_streak"] == 0
    st["summary_day"] = "2000-01-01"                                                           # next daily attempt, now succeeding
    (tmp_path / "watch_state.json").write_text(json.dumps(st))
    res["fail"] = False
    st, _ = _loop(monkeypatch, tmp_path, 1, write_all=OK_EXPORT, summary_hour=0)
    assert st["last_error"] is None and st["last_error_last"]["where"] == "budget_policy"


# ------------------------------------------------------------------ 3. export retry / failing
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
    _loop(monkeypatch, tmp_path, 1, write_all=wa)
    assert n["calls"] == 1
    s = json.loads((tmp_path / "watch_state.json").read_text())
    s["export_next_retry"] = time.time() - 1
    (tmp_path / "watch_state.json").write_text(json.dumps(s))
    t1 = time.time()
    st, _ = _loop(monkeypatch, tmp_path, 1, write_all=wa)
    assert n["calls"] == 2 and 599 <= st["export_next_retry"] - t1 <= 605 and st["export_fail_n"] == 2
    st["export_next_retry"] = time.time() - 1
    (tmp_path / "watch_state.json").write_text(json.dumps(st))
    n["fail"] = False
    st, _ = _loop(monkeypatch, tmp_path, 1, write_all=wa)
    assert n["calls"] == 3 and st["export_error"] is None and "export_next_retry" not in st and st["export_fail_n"] == 0
    _loop(monkeypatch, tmp_path, 1, write_all=wa)
    assert n["calls"] == 3


def _quiet(monkeypatch):
    monkeypatch.setattr(watch.shutil, "disk_usage", lambda p: type("U", (), {"free": 90, "total": 100})())
    monkeypatch.setattr(watch.budget, "task_spent", lambda *a, **k: 0.0)


def test_export_failing_issue(monkeypatch):
    _quiet(monkeypatch)
    assert "export_failing" not in watch.check_all(NOW, {"export_ts": NOW.timestamp() - 600, "export_fail_n": 2})
    assert "export_failing" in watch.check_all(NOW, {"export_ts": NOW.timestamp() - 600, "export_fail_n": 3, "export_error": {"type": "OSError"}})
    assert "export_failing" in watch.check_all(NOW, {"export_ts": NOW.timestamp() - 7300})
    assert "export_failing" not in watch.check_all(NOW, {})


# ------------------------------------------------------------------ B. watchdog self-health
def test_watchdog_degraded_after_five_failed_cycles_rate_limited(monkeypatch, tmp_path):
    def bad(now, wst=None):
        raise RuntimeError("status files unreadable")
    st, sent = _loop(monkeypatch, tmp_path, 4, check=bad, write_all=OK_EXPORT)
    assert sent == [] and st["fail_streak"] == 4
    st, sent = _loop(monkeypatch, tmp_path, 3, check=bad, write_all=OK_EXPORT)
    assert len([m for m in sent if "watchdog_degraded" in m]) == 1 and st["fail_streak"] == 7      # one message, not one per cycle
    assert "check_all" in sent[0]
    st["degraded_alert_ts"] -= watch.REALERT_S + 1                                                   # 6 h later: one more
    (tmp_path / "watch_state.json").write_text(json.dumps(st))
    st, sent = _loop(monkeypatch, tmp_path, 1, check=bad, write_all=OK_EXPORT)
    assert len([m for m in sent if "watchdog_degraded" in m]) == 1
    st, sent = _loop(monkeypatch, tmp_path, 1, write_all=OK_EXPORT)                                  # healthy again
    assert sent == ["[watchdog] RECOVERED watchdog_degraded"] and st["fail_streak"] == 0 and "degraded_alert_ts" not in st


# ------------------------------------------------------------------ D. atomic state write / pending alerts
def test_state_write_is_atomic_and_failure_does_not_kill_loop(monkeypatch, tmp_path):
    _state(tmp_path, marker="keep")
    real = os.replace

    def broken(a, b):
        raise OSError("rename failed")
    monkeypatch.setattr(watch.os, "replace", broken)
    monkeypatch.setattr(watch, "STATE", tmp_path / "watch_state.json")
    monkeypatch.setattr(watch, "check_all", lambda now, wst=None: {})
    n = {"i": 0}
    watch.run_forever(stop=lambda: n.__setitem__("i", n["i"] + 1) or n["i"] > 1, sleep=lambda s: None, send=lambda m: None)
    assert json.loads((tmp_path / "watch_state.json").read_text()) == {"marker": "keep"}            # old file intact, no truncation
    assert not (tmp_path / "watch_state.json.tmp").exists()
    monkeypatch.setattr(watch.os, "replace", real)
    n["i"] = 0
    watch.run_forever(stop=lambda: n.__setitem__("i", n["i"] + 1) or n["i"] > 1, sleep=lambda s: None, send=lambda m: None)
    assert "heartbeat" in json.loads((tmp_path / "watch_state.json").read_text())


def test_send_failure_keeps_alert_pending(monkeypatch, tmp_path):
    chk = lambda now, wst=None: {"a": "stale"}      # noqa: E731
    outcome = {"fail": True}
    got = []

    def send(m):
        if outcome["fail"]:
            raise ConnectionError("telegram down")
        got.append(m)
    st, _ = _loop(monkeypatch, tmp_path, 1, check=chk, write_all=OK_EXPORT, send=send)
    assert "a" not in st["open"] and st["last_error"]["where"] == "send_alerts"
    outcome["fail"] = False
    st, _ = _loop(monkeypatch, tmp_path, 1, check=chk, write_all=OK_EXPORT, send=send)
    assert got == ["[watchdog] ISSUE a: stale"] and "a" in st["open"] and st["last_error"] is None
    # notify.send never raises: it reports {'sent': False}; that must count as undelivered too
    st, _ = _loop(monkeypatch, tmp_path, 1, check=lambda now, wst=None: {"a": "stale", "b": "x"}, write_all=OK_EXPORT,
                  send=lambda m: {"sent": False, "reason": "http 500"})
    assert "b" not in st["open"]
    st, _ = _loop(monkeypatch, tmp_path, 1, check=lambda now, wst=None: {}, write_all=OK_EXPORT, send=lambda m: {"sent": False})
    assert "a" in st["open"]                                                                          # failed RECOVERED stays open -> retried


# ------------------------------------------------------------------ 4/A. KIS pacing alert
def _k(now_kst, calls, lim, state="collecting", cycle=None, errors=0, err_msg=None):
    cyc = cycle or now_kst
    return {"state": state, "heartbeat": now_kst.isoformat(), "last_cycle": {"at": cyc.isoformat(), "new_rows": 1},
            "calls_today": calls, "rate_limited_today": lim, "errors_today": errors,
            "last_error": {"at": now_kst.isoformat(), "msg": err_msg} if err_msg else None}


def _at(h, m=0, day=28):
    return dt.datetime(2026, 10, day, h, m, tzinfo=KST)


def test_kis_alert_thresholds_and_wording():
    f = watch.kis_ratelimit_issue
    now = _at(12)
    m = f(_k(now, 2374, 700), now, {})
    assert "700" in m and "2374" in m and "29.5%" in m and "not a hard quota" in m
    assert f(_k(now, 2374, 395), now, {}) is None                       # 16.6% = normal per-second pacing, below 25%
    assert f(_k(now, 199, 150), now, {}) is None                        # total < 200
    assert f(_k(now, 200, 50), now, {}) is None                         # exactly 25% is not "above"
    assert f(_k(now, 200, 51), now, {}) is not None
    assert f({"state": "collecting", "heartbeat": "garbage", "last_cycle": {"at": "x"}, "calls_today": 900, "rate_limited_today": 800}, now, {}) is None


def test_kis_stale_counters_not_used_at_open_holiday_weekend():
    f = watch.kis_ratelimit_issue
    yest = _at(15, 29, day=27)
    at_open = _at(9, 0)
    assert f(_k(at_open, 2000, 900, state="sleeping_between_cycles", cycle=yest), at_open, {}) is None      # yesterday's cycle + counters
    assert f(_k(at_open, 2000, 900, cycle=_at(8, 59)), at_open, {}) is None                                # cycle before the open
    assert f(_k(_at(12), 2000, 900, state="no_data_today(holiday?)"), _at(12), {}) is None                  # holiday
    assert f(_k(_at(12), 2000, 900, state="error_backoff"), _at(12), {}) is None
    sat = _at(12, day=31)
    assert f(_k(sat, 2000, 900), sat, {}) is None
    assert f(_k(_at(12), 2000, 900), _at(12), {}) is not None                                               # control: the same numbers evaluate in session


def test_kis_hysteresis_no_flapping():
    f, w = watch.kis_ratelimit_issue, {}
    now = _at(12)
    seq = [(1000, 300, True), (1000, 200, True), (1000, 120, True), (1000, 99, False), (1000, 200, False), (1000, 251, True), (1000, 260, True)]
    for total, lim, want in seq:
        assert bool(f(_k(now, total, lim), now, w)) is want, (total, lim)


def test_kis_out_of_session_holds_state_without_recovered_or_realert():
    w = {"open": {}}
    now = _at(12)
    iss = {"kis_ratelimit": watch.kis_ratelimit_issue(_k(now, 1000, 400), now, w)}
    msgs, w = watch.diff_alerts(iss, w, 1000)
    assert len(msgs) == 1
    for later in (_at(15, 40), _at(23, 0), _at(0, 5, day=29), _at(8, 59, day=29)):        # after session, midnight, before next open
        k = _k(later, 1000, 400, state="waiting_market_open", cycle=_at(15, 29))
        iss = {"kis_ratelimit": watch.kis_ratelimit_issue(k, later, w)}
        assert iss["kis_ratelimit"]
        msgs, w = watch.diff_alerts(iss, w, 1000 + watch.REALERT_S + 5)
        assert msgs == [] and "kis_ratelimit" in w["open"]                            # silent: neither re-alert nor RECOVERED
    sat = _at(12, day=31)
    iss = {"kis_ratelimit": watch.kis_ratelimit_issue(_k(sat, 5, 0), sat, w)}
    msgs, w = watch.diff_alerts(iss, w, 1000 + 2 * watch.REALERT_S)
    assert msgs == []


def test_kis_new_day_resets_silently_and_exhausted_retries_alert_immediately():
    w = {"open": {}}
    d1 = _at(12)
    iss = {"kis_ratelimit": watch.kis_ratelimit_issue(_k(d1, 1000, 400), d1, w)}
    _, w = watch.diff_alerts(iss, w, 1000)
    d2 = _at(9, 30, day=29)                                   # Thu: fresh counters, low ratio
    iss = {k: v for k, v in {"kis_ratelimit": watch.kis_ratelimit_issue(_k(d2, 40, 1), d2, w)}.items() if v}
    msgs, w = watch.diff_alerts(iss, w, 2000)
    assert iss == {} and msgs == [] and w["open"] == {}      # day rollover is not a RECOVERED event
    w2 = {}
    f = watch.kis_ratelimit_issue
    assert f(_k(d2, 40, 1, errors=2), d2, w2) is None        # first sight: baseline, no alert for pre-existing errors
    m = f(_k(d2, 60, 2, errors=3, err_msg="HTTP 429 rt_cd=-1 msg_cd=None retries exhausted"), d2, w2)
    assert m and "retries exhausted" in m and "errors_today=3" in m
    assert f(_k(d2, 60, 2, errors=3), d2, {"kis_rl": {"day": d2.date().isoformat(), "errors_seen": 3}}) is None


def test_check_all_emits_one_kis_issue_with_existing_cadence(monkeypatch, tmp_path):
    _quiet(monkeypatch)
    monkeypatch.setattr(kisintra, "STATUS", tmp_path / "kis.json")
    now = dt.datetime(2026, 10, 28, 3, 0, tzinfo=UTC)
    (tmp_path / "kis.json").write_text(json.dumps(_k(now.astimezone(KST), 1000, 400)))
    wst = {}
    iss = watch.check_all(now, wst)
    assert [k for k in iss if k.startswith("kis_ratelimit")] == ["kis_ratelimit"]
    msgs, st = watch.diff_alerts(iss, wst, 1000)
    assert sum("kis_ratelimit" in m for m in msgs) == 1
    msgs, st = watch.diff_alerts(watch.check_all(now, st), st, 1100)
    assert not any("kis_ratelimit" in m for m in msgs)
    msgs, st = watch.diff_alerts(watch.check_all(now, st), st, 1000 + watch.REALERT_S + 1)
    assert sum("kis_ratelimit" in m for m in msgs) == 1


# ------------------------------------------------------------------ 2/E. forward: REAL research.get_signal path with growing klines
N0, N1 = 1200, 1248            # 1h bars; 4h = N/4, 15m = N*4 (all start 2024-01-01)
FREQ = {"15m": ("15min", 4.0), "1h": ("1h", 1.0), "4h": ("4h", 0.25)}


def _frames(n):
    out = {}
    for sym, seed in (("BTC/USDT", 3), ("ETH/USDT", 5)):
        for tf, (fr, mult) in FREQ.items():
            out[(sym, tf)] = make_ohlcv(int(n * mult), seed=seed + 11, drift=0.0002, freq=fr)
    return out


@pytest.fixture()
def live(tmp_path, monkeypatch):
    state = {"f": _frames(N0), "calls": []}
    monkeypatch.setattr(forward, "REG", tmp_path / "reg.json")
    monkeypatch.setattr(research, "_SIG_CACHE", {})
    monkeypatch.setattr(forward, "_SIG_FP", {}, raising=False)

    def load_df(sym, tf):
        state["calls"].append((sym, tf))
        return state["f"][(sym, tf)]
    monkeypatch.setattr(research, "load_df", load_df)                     # real research.get_signal / pool strategies / overlays below this
    monkeypatch.setattr(research, "fund_arr", lambda sym, d, tf: np.zeros(len(d)))
    from tp import fomc
    monkeypatch.setattr(fomc, "statement_times", lambda: [dt.datetime(2024, 1, 20, 18, tzinfo=UTC), dt.datetime(2024, 2, 5, 18, tzinfo=UTC)])
    return state


def _reg(state):
    t = state["f"][("BTC/USDT", "1h")].index[800].strftime("%Y-%m-%dT%H:%M:%SZ")
    return {k: t for k in forward.CANDIDATES}


@pytest.mark.parametrize("name", ["C3_trend_mtf_ls_BTC_1h", "C3f_fomc", "C2_btc_alt_long_ETH_4h"])
def test_forward_real_signal_path_survives_kline_growth(live, name):
    reg = _reg(live)
    d, sig, _, _ = forward.candidate_signal(name)
    n0 = len(d)
    assert len(sig) == n0 and forward.evaluate(name, reg)["status"] != "ERROR"
    live["f"] = _frames(N1)                                                  # tp-news appended bars while tp-watch kept running
    d, sig, _, _ = forward.candidate_signal(name)
    assert len(d) > n0 and len(sig) == len(d) and sig.index.equals(d.index)
    r = forward.evaluate(name, reg)
    assert r["status"] != "ERROR" and r["bars"] > 0


def test_forward_a1_recomputes_every_timeframe_and_loads_each_once(live):
    forward.candidate_signal("C4_A1_rule_BTC")
    live["f"] = _frames(N1)
    live["calls"].clear()
    d, sig, _, _ = forward.candidate_signal("C4_A1_rule_BTC")
    assert len(sig) == len(d) == int(N1 * 4)
    for st, side, tf, _w in research.A1_TABLE.values():                      # no component signal left at the old length
        assert len(research._SIG_CACHE[(st, side, "BTC/USDT", tf)]) == int(N1 * FREQ[tf][1])
    per = [c for c in live["calls"] if c[0] == "BTC/USDT"]
    assert per.count(("BTC/USDT", "15m")) == 1 and per.count(("BTC/USDT", "1h")) == 1      # frames reused, one snapshot per call


def test_forward_btc_context_lagging_is_refused_not_cached_flat(live):
    f = live["f"]
    f[("BTC/USDT", "4h")] = f[("BTC/USDT", "4h")].iloc[:-3]                  # ETH 4h frame is ahead of the BTC context
    with pytest.raises(ValueError, match="BTC context"):
        forward.candidate_signal("C2_btc_alt_long_ETH_4h")
    assert ("coin_btc_regime_alt", "long", "ETH/USDT", "4h") not in research._SIG_CACHE
    row = forward.evaluate_all()[3]
    assert row["candidate"] == "C2_btc_alt_long_ETH_4h" and row["status"] == "ERROR" and "BTC context" in row["note"]
    live["f"] = _frames(N0)                                                  # BTC catches up -> works
    assert forward.evaluate("C2_btc_alt_long_ETH_4h", _reg(live))["status"] != "ERROR"


def test_forward_same_length_but_shifted_frame_recomputes(live):
    forward.candidate_signal("C3_trend_mtf_ls_BTC_1h")
    f = live["f"][("BTC/USDT", "1h")]
    live["f"][("BTC/USDT", "1h")] = f.shift(-1, freq="1h")                   # same length, different last bar
    d, sig, _, _ = forward.candidate_signal("C3_trend_mtf_ls_BTC_1h")
    assert sig.index.equals(d.index) and d.index[-1] == f.index[-1] - pd.Timedelta(hours=1)
    assert forward._SIG_FP[("coin_trend_mtf", "ls", "BTC/USDT", "1h")][0][1] == d.index[-1].value


def test_forward_error_note_is_scrubbed(live, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("leak sk-abcdefghijklmnopqrstuv " + "x" * 500)
    monkeypatch.setattr(forward, "evaluate", boom)
    rows = forward.evaluate_all()
    assert all(r["status"] == "ERROR" and "sk-abcdefghij" not in r["note"] and len(r["note"]) <= 200 for r in rows)
