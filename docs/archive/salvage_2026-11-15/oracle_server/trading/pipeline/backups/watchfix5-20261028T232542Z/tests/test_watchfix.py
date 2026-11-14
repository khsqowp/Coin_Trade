"""watch fixes: structured last_error + resolution, export retry/failing, KIS pacing alert (stale guard, hysteresis, hold), watchdog self-health,
atomic state write, pending alerts, and forward stale-signal-cache regressions through the REAL research.get_signal path."""
import datetime as dt
import json
import os
import time
import types

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
    monkeypatch.setattr(watch, "_MEM", {})
    monkeypatch.setattr(watch, "_TG_LOGGED", {"v": False}, raising=False)
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
    st["degraded_try_ts"] -= watch.REALERT_S + 1
    st["degraded_alert_ts"] -= watch.REALERT_S + 1                                                   # 6 h later: one more
    (tmp_path / "watch_state.json").write_text(json.dumps(st))
    st, sent = _loop(monkeypatch, tmp_path, 1, check=bad, write_all=OK_EXPORT)
    assert len([m for m in sent if "watchdog_degraded" in m]) == 1
    st, sent = _loop(monkeypatch, tmp_path, 1, write_all=OK_EXPORT)                                  # healthy again
    assert sent == ["[watchdog] RECOVERED watchdog_degraded"] and st["fail_streak"] == 0 and "degraded_alert_ts" not in st


# ------------------------------------------------------------------ D. atomic state write / pending alerts
def test_state_write_is_atomic_and_failure_does_not_kill_loop(monkeypatch, tmp_path):
    _state(tmp_path, marker="keep")
    monkeypatch.setattr(watch, "SUMMARY_HOUR_UTC", 25)
    monkeypatch.setattr(watch, "_MEM", {})
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


def _rewind(tmp_path):
    f = tmp_path / "watch_state.json"
    st = json.loads(f.read_text())
    for e in (st.get("send_retry") or {}).values():
        e["next"] = 0
    f.write_text(json.dumps(st))


def test_send_failure_keeps_alert_pending(monkeypatch, tmp_path):
    chk = lambda now, wst=None: {"a": "stale"}      # noqa: E731
    outcome = {"fail": True}
    got = []

    def send(m):
        if outcome["fail"]:
            raise ConnectionError("telegram down")
        got.append(m)
    st, _ = _loop(monkeypatch, tmp_path, 1, check=chk, write_all=OK_EXPORT, send=send)
    assert "a" not in st["open"] and st["last_error"]["where"] == "send_alerts" and st["send_retry"]["alert:a"]["n"] == 1
    outcome["fail"] = False
    _rewind(tmp_path)                                                       # backoff elapsed
    st, _ = _loop(monkeypatch, tmp_path, 1, check=chk, write_all=OK_EXPORT, send=send)
    assert got == ["[watchdog] ISSUE a: stale"] and "a" in st["open"] and st["last_error"] is None and not st.get("send_retry")
    # notify.send never raises: it reports {'sent': False}; that must count as undelivered too
    st, _ = _loop(monkeypatch, tmp_path, 1, check=lambda now, wst=None: {"a": "stale", "b": "x"}, write_all=OK_EXPORT,
                  send=lambda m: {"sent": False, "reason": "http 500"})
    assert "b" not in st["open"]
    _rewind(tmp_path)
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


def test_kis_day_rollover_sends_recovered_and_skips_yesterdays_counters():
    f, w = watch.kis_ratelimit_issue, {"open": {}}
    d1 = _at(12)
    iss = {"kis_ratelimit": f(_k(d1, 1000, 400), d1, w)}
    msgs, w = watch.diff_alerts(iss, w, 1000)
    assert len(msgs) == 1
    d2 = _at(9, 5, day=29)                                    # Thu: first cycle of the day still carries Wednesday's counters (written at loop start)
    c1 = _at(9, 4, day=29)
    iss = {k: v for k, v in {"kis_ratelimit": f(_k(d2, 1000, 400, cycle=c1), d2, w)}.items() if v}
    msgs, w = watch.diff_alerts(iss, w, 1100)
    assert iss == {} and msgs == ["[watchdog] RECOVERED kis_ratelimit"]       # delivered ISSUE ends with RECOVERED, and NO new ISSUE from stale numbers
    d3 = _at(9, 10, day=29)
    iss = {k: v for k, v in {"kis_ratelimit": f(_k(d3, 1000, 400, cycle=c1), d3, w)}.items() if v}
    assert iss == {}                                          # same cycle again: still awaiting the counter reset
    d4 = _at(9, 15, day=29)
    assert f(_k(d4, 40, 1, cycle=d4), d4, w) is None          # counters dropped -> evaluation resumes, low ratio
    assert f(_k(d4, 400, 200, cycle=d4), d4, w)               # and a genuinely bad day is detected afterwards


def test_kis_rollover_second_cycle_ends_the_wait_even_if_total_is_not_lower():
    f, w = watch.kis_ratelimit_issue, {}
    d1 = _at(12)
    f(_k(d1, 300, 10), d1, w)
    d2 = _at(9, 5, day=29)
    assert f(_k(d2, 400, 200, cycle=_at(9, 4, day=29)), d2, w) is None       # first cycle: awaiting
    d3 = _at(9, 10, day=29)
    assert f(_k(d3, 500, 250, cycle=d3), d3, w)                              # second cycle completed: counters are today's (50% -> ISSUE)
    assert w["kis_rl"]["await_reset"] is False


EXH = "HTTP 429 rt_cd=-1 msg_cd=None retries exhausted"


def _ex(now, at, calls=60, lim=2, msg=EXH):
    k = _k(now, calls, lim)
    k["last_error"] = {"at": at.isoformat(), "msg": msg}
    return k


def test_kis_exhausted_latch_needs_three_fresh_events_and_autoclears():
    f, w = watch.kis_ratelimit_issue, {}
    t = _at(10, 0)
    assert f(_ex(t, _at(9, 30)), t, w) is None                          # first sight: pre-existing last_error is only a baseline
    t1 = _at(10, 5)
    assert f(_ex(t1, _at(10, 4)), t1, w) is None                        # event 1
    assert f(_ex(t1, _at(10, 4)), t1, w) is None                        # same last_error.at seen again: NOT a new event
    assert f(_ex(_at(10, 12), _at(10, 11)), _at(10, 12), w) is None     # event 2
    m = f(_ex(_at(10, 20), _at(10, 19)), _at(10, 20), w)                # event 3 within 30 min -> latch
    assert m and "retries-exhausted" in m and "not a hard quota" in m
    assert f(_ex(_at(10, 50), _at(10, 19)), _at(10, 50), w)             # still latched, no new events, < 60 min
    assert f(_ex(_at(11, 21), _at(10, 19)), _at(11, 21), w) is None     # 62 min quiet -> auto-clears (day ratio is only 3%)
    assert w["kis_rl"]["ex_active"] is False


def test_kis_exhausted_ignores_old_day_slow_and_non_exhausted_errors():
    f = watch.kis_ratelimit_issue
    w = {}
    t = _at(10, 0)
    f(_ex(t, _at(9, 0)), t, w)
    yday = _at(23, 0, day=27)
    for i, at in enumerate((yday, yday, yday)):
        assert f(_ex(_at(10, 5 + i), at), _at(10, 5 + i), w) is None    # not today's date / not newer than seen
    w = {}
    f(_ex(t, _at(9, 0)), t, w)
    for n, (h, mi) in enumerate(((10, 1), (10, 40), (11, 20))):         # three events but spread over > 30 min
        assert f(_ex(_at(h, mi + 1), _at(h, mi)), _at(h, mi + 1), w) is None
    w = {}
    f(_ex(t, _at(9, 0)), t, w)
    for mi in (1, 2, 3, 4):
        assert f(_ex(_at(10, mi + 1), _at(10, mi), msg="some other error"), _at(10, mi + 1), w) is None


def test_kis_calls_counter_decrease_clears_latch_silently():
    f, w = watch.kis_ratelimit_issue, {"open": {}}
    now = _at(12)
    assert f(_k(now, 1000, 400), now, w)
    _, w = watch.diff_alerts({"kis_ratelimit": w["kis_rl"]["msg"]}, w, 1000)
    now2 = _at(12, 5)
    assert f(_k(now2, 90, 1), now2, w) is None                          # counters went DOWN inside the day (reset race)
    assert "kis_ratelimit" not in w["open"]


def test_kis_garbled_status_does_not_raise():
    f = watch.kis_ratelimit_issue
    now = _at(12)
    for k in ({"state": "collecting", "last_cycle": "oops", "calls_today": 5}, {"state": "collecting", "last_cycle": None},
              {"state": "collecting", "last_cycle": {"at": now.isoformat()}, "calls_today": "x", "last_error": "str"}, None, []):
        assert f(k, now, {}) is None
    assert f(_k(now, 1000, 400), now, {"kis_rl": "garbage"}) is not None


def test_kis_stale_heartbeat_holds_issue_without_flap(monkeypatch, tmp_path):
    _quiet(monkeypatch)
    monkeypatch.setattr(kisintra, "STATUS", tmp_path / "kis.json")
    now = dt.datetime(2026, 10, 28, 3, 0, tzinfo=UTC)
    (tmp_path / "kis.json").write_text(json.dumps(_k(now.astimezone(KST), 1000, 400)))
    wst = {}
    iss = watch.check_all(now, wst)
    msgs, st = watch.diff_alerts(iss, wst, 1000)
    assert len([m for m in msgs if "kis_ratelimit" in m]) == 1
    later = now + dt.timedelta(minutes=30)                                  # collector heartbeat is 30 min old
    iss = watch.check_all(later, st)
    assert "kis_ratelimit" in iss and "kis_heartbeat" in iss
    msgs, st = watch.diff_alerts(iss, st, 1100)
    assert not [m for m in msgs if "kis_ratelimit" in m]                    # no RECOVERED while the collector is silent
    (tmp_path / "kis.json").write_text(json.dumps(_k(later.astimezone(KST), 1100, 440)))
    iss = watch.check_all(later, st)
    msgs, st = watch.diff_alerts(iss, st, 1200)
    assert "kis_ratelimit" in iss and not [m for m in msgs if "kis_ratelimit" in m]      # and no new ISSUE when it returns
    (tmp_path / "kis.json").unlink()                                        # missing status file also holds
    assert "kis_ratelimit" in watch.check_all(later, st)


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
    monkeypatch.setattr(forward, "_NEEDS_BTC", {}, raising=False)
    monkeypatch.setattr(forward, "llm_rm_series", lambda index, tf: np.ones(len(index)))      # hermetic: no host regime log

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
    row = {r["candidate"]: r for r in forward.evaluate_all()}["C2_btc_alt_long_ETH_4h"]
    assert row["status"] == "ERROR" and "BTC context" in row["note"]
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


def test_forward_revised_last_bar_at_equal_length_recomputes(live):
    key = ("coin_trend_mtf", "ls", "BTC/USDT", "1h")
    forward.candidate_signal("C3_trend_mtf_ls_BTC_1h")
    first, fp1 = research._SIG_CACHE[key], forward._SIG_FP[key]
    f = live["f"][("BTC/USDT", "1h")].copy()
    f.iloc[-1, f.columns.get_loc("close")] *= 1.01                           # exchange revised the last bar: same length, same index
    live["f"][("BTC/USDT", "1h")] = f
    forward.candidate_signal("C3_trend_mtf_ls_BTC_1h")
    assert research._SIG_CACHE[key] is not first and forward._SIG_FP[key] != fp1 and forward._SIG_FP[key][0][2] != fp1[0][2]
    again = research._SIG_CACHE[key]
    forward.candidate_signal("C3_trend_mtf_ls_BTC_1h")                       # untouched data -> cache hit
    assert research._SIG_CACHE[key] is again


def test_forward_cache_hit_does_not_reload_pool_module(live, monkeypatch):
    from tp import pool
    forward.candidate_signal("C2_btc_alt_long_ETH_4h")
    n = {"c": 0}
    real = pool.load
    monkeypatch.setattr(pool, "load", lambda name: n.__setitem__("c", n["c"] + 1) or real(name))
    forward.candidate_signal("C2_btc_alt_long_ETH_4h")
    assert n["c"] == 0


# ------------------------------------------------------------------ 1/3/4/6/7 round 3
def _broken_replace(monkeypatch):
    def broken(a, b):
        raise OSError("read-only file system")
    monkeypatch.setattr(watch.os, "replace", broken)


def test_state_write_failure_does_not_cause_alert_summary_export_storm(monkeypatch, tmp_path, capsys):
    from tp import budget_policy
    _broken_replace(monkeypatch)
    prop = {"n": 0}
    monkeypatch.setattr(budget_policy, "propose", lambda now: prop.__setitem__("n", prop["n"] + 1) or ("PROPOSAL TEXT", {}))
    monkeypatch.setattr(watch, "daily_summary", lambda now: "SUMMARY")
    exp = {"n": 0}
    sent = []
    monkeypatch.setattr(watch, "STATE", tmp_path / "watch_state.json")
    monkeypatch.setattr(watch, "_MEM", {})
    monkeypatch.setattr(watch, "SUMMARY_HOUR_UTC", 0)
    monkeypatch.setattr(watch, "check_all", lambda now, wst=None: {"a": "stale"})
    from tp import hermesx
    monkeypatch.setattr(hermesx, "write_all", lambda now: exp.__setitem__("n", exp["n"] + 1) or {"withheld": {}})
    n = {"i": 0}
    watch.run_forever(stop=lambda: n.__setitem__("i", n["i"] + 1) or n["i"] > 6, sleep=lambda s: None, send=sent.append)
    assert sent.count("[watchdog] ISSUE a: stale") == 1 and sent.count("SUMMARY") == 1 and sent.count("PROPOSAL TEXT") == 1
    assert prop["n"] == 1 and exp["n"] == 1
    assert not (tmp_path / "watch_state.json").exists()
    mem = watch._MEM["st"]
    assert mem["last_error"]["where"] == "state_write" and mem["fail_streak"] == 6
    assert len([m for m in sent if "watchdog_degraded" in m]) == 1                  # failed-write cycles count towards degraded, once
    assert "state write failed" in capsys.readouterr().err


def test_state_file_garbage_or_non_dict_is_tolerated(monkeypatch, tmp_path):
    (tmp_path / "watch_state.json").write_text("[1, 2, 3]")
    st, _ = _loop(monkeypatch, tmp_path, 1, write_all=OK_EXPORT)
    assert isinstance(st, dict) and "heartbeat" in st
    (tmp_path / "watch_state.json").write_text(json.dumps({"open": "bad", "kis_rl": 5, "send_retry": []}))
    st, _ = _loop(monkeypatch, tmp_path, 1, write_all=OK_EXPORT)
    assert st["open"] == {} and "heartbeat" in st


def test_failed_send_stops_the_cycle_and_backs_off_exponentially(monkeypatch, tmp_path):
    calls = {"n": 0}

    def down(m):
        calls["n"] += 1
        return {"sent": False, "reason": "http 500"}
    chk = lambda now, wst=None: {k: "x" for k in "abcde"}      # noqa: E731
    st, _ = _loop(monkeypatch, tmp_path, 1, check=chk, write_all=OK_EXPORT, send=down)
    assert calls["n"] == 1 and st["open"] == {}                                   # five alerts, ONE request
    t = time.time()
    assert 58 <= st["send_retry"]["alert:a"]["next"] - t <= 62
    _loop(monkeypatch, tmp_path, 5, check=chk, write_all=OK_EXPORT, send=down)    # inside the backoff window: no request at all
    assert calls["n"] == 1
    for n_fail, want in ((2, 120), (3, 240), (4, 480), (5, 900), (6, 900)):
        _rewind(tmp_path)
        t = time.time()
        st, _ = _loop(monkeypatch, tmp_path, 1, check=chk, write_all=OK_EXPORT, send=down)
        assert st["send_retry"]["alert:a"]["n"] == n_fail and want - 3 <= st["send_retry"]["alert:a"]["next"] - t <= want + 3
    assert calls["n"] == 6


def test_telegram_disabled_is_not_a_failure(monkeypatch, tmp_path, capsys):
    calls = {"n": 0}

    def off(m):
        calls["n"] += 1
        return {"sent": False, "reason": "disabled: Telegram token/chat id not configured"}
    chk = lambda now, wst=None: {k: "x" for k in "abc"}      # noqa: E731
    st, _ = _loop(monkeypatch, tmp_path, 6, check=chk, write_all=OK_EXPORT, send=off)
    assert calls["n"] == 3 and set(st["open"]) == {"a", "b", "c"}                 # consumed once, never retried or re-sent
    assert st["last_error"] is None and st["fail_streak"] == 0 and "degraded_alert_ts" not in st and not st.get("send_retry")
    assert capsys.readouterr().err.count("not configured") == 1                   # logged once per process
    assert "tg_disabled_logged" not in st and st["telegram_disabled"]["since"]     # status is persisted, the log-once marker is not


def test_send_time_is_capped_per_cycle(monkeypatch, tmp_path):
    monkeypatch.setattr(watch, "SEND_BUDGET_S", -1)
    calls = {"n": 0}
    st, _ = _loop(monkeypatch, tmp_path, 1, check=lambda now, wst=None: {"a": "x", "b": "y"}, write_all=OK_EXPORT,
                  send=lambda m: calls.__setitem__("n", calls["n"] + 1))
    assert calls["n"] == 1 and set(st["open"]) == {"a"}          # the budget clock starts at the first send, which is always allowed


def test_summary_not_consumed_until_delivered_then_retried(monkeypatch, tmp_path):
    from tp import budget_policy
    monkeypatch.setattr(watch, "daily_summary", lambda now: "SUMMARY")
    prop = {"n": 0}
    monkeypatch.setattr(budget_policy, "propose", lambda now: prop.__setitem__("n", prop["n"] + 1) or ("PROPOSAL", {}))
    ok = {"v": False}
    got = []

    def send(m):
        if not ok["v"]:
            return {"sent": False, "reason": "http 500"}
        got.append(m)
    st, _ = _loop(monkeypatch, tmp_path, 1, write_all=OK_EXPORT, send=send, summary_hour=0)
    assert "summary_day" not in st and prop["n"] == 0 and st["last_error"]["where"] == "daily_summary"
    _loop(monkeypatch, tmp_path, 3, write_all=OK_EXPORT, send=send, summary_hour=0)       # backoff: nothing happens
    assert prop["n"] == 0 and got == []
    ok["v"] = True
    _rewind(tmp_path)
    st, _ = _loop(monkeypatch, tmp_path, 1, write_all=OK_EXPORT, send=send, summary_hour=0)
    assert got == ["SUMMARY", "PROPOSAL"] and st["summary_day"] and prop["n"] == 1 and "pending_proposal" not in st


def _proposal_env(monkeypatch, tmp_path, status="pending", to_cap=0.6):
    from tp import budget_policy
    f = tmp_path / "prop.json"
    f.write_text(json.dumps({"created_at": "2026-10-28T00:00:00Z", "from_cap": 0.3, "to_cap": to_cap, "status": status, "checks": []}))
    monkeypatch.setattr(budget_policy, "PROPOSAL", f)
    monkeypatch.setattr(budget_policy, "check", lambda now: {"eligible": True, "cap_now": 0.3, "next_cap": 0.6, "llm_cost_usd": 0.1, "sharpe_adj": 1.0,
                                                             "net_return": 0.1, "checks": [{"name": "x", "value": 1, "ok": True}]})
    return f


def test_budget_proposal_survives_delivery_failure_and_is_rerendered(monkeypatch, tmp_path):
    """budget_policy.propose() writes 'pending' to disk and never returns the text again: the watch state keeps only a marker and re-renders."""
    from tp import budget_policy
    _proposal_env(monkeypatch, tmp_path)
    monkeypatch.setattr(watch, "daily_summary", lambda now: "SUMMARY")
    prop = {"n": 0}
    monkeypatch.setattr(budget_policy, "propose", lambda now: prop.__setitem__("n", prop["n"] + 1) or ("FRESH TEXT", {}))
    ok = {"v": False}
    got = []

    def send(m):
        if m != "SUMMARY" and not ok["v"]:
            return {"sent": False, "reason": "http 500"}
        got.append(m)
    st, _ = _loop(monkeypatch, tmp_path, 1, write_all=OK_EXPORT, send=send, summary_hour=0)
    assert got == ["SUMMARY"] and set(st["pending_proposal"]) == {"at"} and st["last_error"]["where"] == "proposal" and prop["n"] == 1
    ok["v"] = True
    _rewind(tmp_path)
    st, _ = _loop(monkeypatch, tmp_path, 2, write_all=OK_EXPORT, send=send, summary_hour=0)
    assert len(got) == 2 and got[1].startswith("[예산 증액 제안") and "FRESH TEXT" not in got and "pending_proposal" not in st and prop["n"] == 1


def test_pending_proposal_dropped_when_old_or_no_longer_pending(monkeypatch, tmp_path):
    f = _proposal_env(monkeypatch, tmp_path)
    got = []
    old = time.time() - 3 * 86400 - 60
    _state(tmp_path, pending_proposal={"at": old})
    st, _ = _loop(monkeypatch, tmp_path, 1, write_all=OK_EXPORT, send=got.append)
    assert got == [] and "pending_proposal" not in st                               # older than 3 days
    _state(tmp_path, pending_proposal={"at": time.time()})
    f.write_text(json.dumps({"to_cap": 0.6, "status": "approved"}))
    st, _ = _loop(monkeypatch, tmp_path, 1, write_all=OK_EXPORT, send=got.append)
    assert got == [] and "pending_proposal" not in st                               # owner already acted
    _proposal_env(monkeypatch, tmp_path)
    _state(tmp_path, pending_proposal={"at": time.time()})
    st, _ = _loop(monkeypatch, tmp_path, 1, write_all=OK_EXPORT, send=got.append)
    assert len(got) == 1 and "pending_proposal" not in st
    _state(tmp_path, pending_proposal="legacy bare text")                          # state written by an older watchdog version
    from tp import budget_policy
    monkeypatch.setattr(budget_policy, "check", lambda now: (_ for _ in ()).throw(RuntimeError("down")))
    st, _ = _loop(monkeypatch, tmp_path, 1, write_all=OK_EXPORT, send=got.append)
    assert got[-1] == "legacy bare text"


def test_degraded_attempts_are_rate_limited_separately(monkeypatch, tmp_path):
    calls = {"n": 0}

    def down(m):
        calls["n"] += 1
        return {"sent": False, "reason": "http 500"}

    def bad(now, wst=None):
        raise RuntimeError("x")
    st, _ = _loop(monkeypatch, tmp_path, 12, check=bad, write_all=OK_EXPORT, send=down)
    assert st["fail_streak"] == 12 and calls["n"] == 1 and "degraded_alert_ts" not in st          # one attempt, then DEGRADED_TRY_S silence


def test_stateless_callers_see_same_issues_and_never_write(monkeypatch, tmp_path):
    _quiet(monkeypatch)
    monkeypatch.setattr(watch, "STATE", tmp_path / "watch_state.json")
    monkeypatch.setattr(watch, "_MEM", {})
    monkeypatch.setattr(kisintra, "STATUS", tmp_path / "kis.json")
    late = dt.datetime(2026, 10, 28, 14, 0, tzinfo=UTC)                               # 23:00 KST, after session
    cyc = _at(15, 29)
    (tmp_path / "kis.json").write_text(json.dumps(dict(_k(late.astimezone(KST), 1000, 400, state="waiting_market_open", cycle=cyc))))
    st = {"open": {"kis_ratelimit": 1.0}, "kis_rl": {"day": "2026-10-28", "active": True, "ratio_active": True, "msg": "KIS pacing held", "calls_seen": 1000}}
    (tmp_path / "watch_state.json").write_text(json.dumps(st))
    before = (tmp_path / "watch_state.json").read_bytes()
    daemon = watch.check_all(late, json.loads(before))
    assert daemon["kis_ratelimit"] == "KIS pacing held"
    assert "kis_ratelimit" not in watch.check_all(late)                                  # stateless call without wst cannot see it
    ro = watch.readonly_state()
    assert watch.check_all(late, ro)["kis_ratelimit"] == "KIS pacing held"
    ro["open"]["zzz"] = 1                                                                # mutating the copy never reaches the file
    assert (tmp_path / "watch_state.json").read_bytes() == before and "zzz" not in watch.readonly_state()["open"]
    seen = []
    monkeypatch.setattr(watch, "check_all", lambda now=None, wst=None: seen.append(wst) or {})
    monkeypatch.setattr(watch.shutil, "disk_usage", lambda p: type("U", (), {"free": 90, "total": 100})())
    from tp import cli, hermesx
    hermesx.status_json(late)
    cli.cmd_watch_check(types.SimpleNamespace(summary=False))
    assert len(seen) == 2 and all(isinstance(w, dict) and w.get("kis_rl", {}).get("active") for w in seen)
    assert (tmp_path / "watch_state.json").read_bytes() == before


def _fwd_file(tmp_path, monkeypatch, rows, mtime):
    from tp import hermesx
    monkeypatch.setattr(hermesx, "EXPORT", tmp_path)
    p = tmp_path / "forward_status.json"
    p.write_text(json.dumps({"candidates": rows}))
    os.utime(p, (mtime, mtime))


def test_forward_error_issue_after_three_hours(monkeypatch, tmp_path):
    _quiet(monkeypatch)
    rows = [{"candidate": "C1", "status": "RUNNING"}, {"candidate": "C3v", "status": "ERROR", "note": "ValueError: boom"}]
    wst = {}
    _fwd_file(tmp_path, monkeypatch, rows, NOW.timestamp())
    assert "forward_error" not in watch.check_all(NOW, wst) and "C3v" in wst["fwd_err_first"]
    t = NOW + dt.timedelta(hours=2, minutes=59)
    _fwd_file(tmp_path, monkeypatch, rows, t.timestamp())
    assert "forward_error" not in watch.check_all(t, wst)
    t = NOW + dt.timedelta(hours=3, minutes=1)
    _fwd_file(tmp_path, monkeypatch, rows, t.timestamp())
    m = watch.check_all(t, wst)["forward_error"]
    assert "C3v" in m and "ValueError: boom" in m
    rows[1]["status"] = "RUNNING"                                                       # recovered -> issue and first-seen cleared
    _fwd_file(tmp_path, monkeypatch, rows, t.timestamp())
    assert "forward_error" not in watch.check_all(t, wst) and wst["fwd_err_first"] == {}
    rows[1]["status"] = "ERROR"
    _fwd_file(tmp_path, monkeypatch, rows, (NOW - dt.timedelta(hours=9)).timestamp())    # stale export file is ignored (export_failing covers it)
    assert "forward_error" not in watch.check_all(t + dt.timedelta(hours=5), {})


# ------------------------------------------------------------------ round 4
class _Resp:
    def __init__(self, code, body=None):
        self.status_code, self._b = code, body or {}

    def json(self):
        return self._b


def test_notify_send_contract_matches_watch_classification(monkeypatch):
    """Real notify.send results (not hand-written dicts) through watch._classify."""
    from tp import notify
    monkeypatch.delenv(notify.TOKEN_ENV, raising=False)
    monkeypatch.delenv(notify.CHAT_ENV, raising=False)
    assert watch._classify(notify.send("x")) == "disabled"
    monkeypatch.setenv(notify.TOKEN_ENV, "123456789:" + "A" * 35)
    monkeypatch.setenv(notify.CHAT_ENV, "42")
    monkeypatch.setattr(notify.time, "sleep", lambda s: None)
    assert watch._classify(notify.send("x", _post=lambda *a, **k: _Resp(200))) == "sent"
    assert watch._classify(notify.send("x", _post=lambda *a, **k: _Resp(401, {"description": "Unauthorized"}))) == "client"
    assert watch._classify(notify.send("x", _post=lambda *a, **k: _Resp(400, {"description": "Bad Request"}))) == "client"
    assert watch._classify(notify.send("x", _post=lambda *a, **k: _Resp(429))) == "failed"
    assert watch._classify(notify.send("x", _post=lambda *a, **k: _Resp(502))) == "failed"

    def boom(*a, **k):
        raise ConnectionError("net")
    assert watch._classify(notify.send("x", _post=boom)) == "failed"


def test_telegram_disabled_is_status_only_not_telegrammed(monkeypatch, tmp_path):
    got = []
    real_check = watch.check_all
    chk = lambda now, wst=None: {"telegram_disabled": "not configured", "a": "stale"}      # noqa: E731
    _loop(monkeypatch, tmp_path, 1, check=chk, write_all=OK_EXPORT, send=got.append)
    assert got == ["[watchdog] ISSUE a: stale"]                                              # never sent to Telegram
    _quiet(monkeypatch)
    monkeypatch.setattr(watch, "check_all", real_check)
    iss = watch.check_all(NOW, {"telegram_disabled": {"since": "2026-10-28T00:00Z"}})
    assert "telegram_disabled" in iss                                                       # but visible to the summary / Hermes export
    assert "telegram_disabled" not in watch.check_all(NOW, {})


def test_client_4xx_backs_off_only_that_key_and_is_dropped_after_five(monkeypatch, tmp_path):
    calls = []

    def send(m):
        calls.append(m)
        if "ISSUE a:" in m:
            return {"sent": False, "reason": "send failed: http 400 Bad Request: can't parse entities"}
        return {"sent": True, "reason": "ok"}
    chk = lambda now, wst=None: {k: "x" for k in "abcde"}      # noqa: E731
    st, _ = _loop(monkeypatch, tmp_path, 1, check=chk, write_all=OK_EXPORT, send=send)
    assert set(st["open"]) == {"b", "c", "d", "e"} and "*" not in st["send_retry"] and st["send_retry"]["alert:a"]["n"] == 1   # no head-of-line blocking
    for n in range(2, 5):
        _rewind(tmp_path)
        st, _ = _loop(monkeypatch, tmp_path, 1, check=chk, write_all=OK_EXPORT, send=send)
        assert st["send_retry"]["alert:a"]["n"] == n and "a" not in st["open"]
    _rewind(tmp_path)
    st, _ = _loop(monkeypatch, tmp_path, 1, check=chk, write_all=OK_EXPORT, send=send)
    assert sum("ISSUE a:" in m for m in calls) == 5 and "a" in st["open"] and not st.get("send_retry")      # dropped = consumed
    assert st["last_error"] is None


def test_global_backoff_clears_after_a_success(monkeypatch, tmp_path):
    ok = {"v": False}
    send = lambda m: {"sent": ok["v"], "reason": "ok" if ok["v"] else "http 503"}      # noqa: E731
    chk = lambda now, wst=None: {"a": "x", "b": "y"}      # noqa: E731
    st, _ = _loop(monkeypatch, tmp_path, 1, check=chk, write_all=OK_EXPORT, send=send)
    assert "*" in st["send_retry"] and "alert:a" in st["send_retry"]
    ok["v"] = True
    _rewind(tmp_path)
    st, _ = _loop(monkeypatch, tmp_path, 1, check=chk, write_all=OK_EXPORT, send=send)
    assert st.get("send_retry") in ({}, None) and set(st["open"]) == {"a", "b"}


def test_backoff_clock_step_back_is_clamped_and_cleared_issue_forgets_backoff(monkeypatch, tmp_path):
    calls = []
    _state(tmp_path, send_retry={"alert:a": {"n": 3, "next": time.time() + 86400}, "*": {"n": 1, "next": time.time() + 7 * 86400}, "alert:gone": {"n": 4, "next": 1}})
    st, _ = _loop(monkeypatch, tmp_path, 1, check=lambda now, wst=None: {"a": "x"}, write_all=OK_EXPORT, send=calls.append)
    assert "alert:gone" not in st["send_retry"] or st.get("send_retry") == {}           # issue cleared before delivery -> backoff counter forgotten
    # the persisted far-future 'next' values (clock stepped back) never park a key for more than the max backoff
    now = time.time()
    assert watch._next({"next": now + 86400}, now) <= now + watch.SEND_BACKOFF_MAX_S
    assert watch._next({"next": "garbage"}, now) == 0.0 and watch._next(None, now) == 0.0


def test_hand_edited_state_values_do_not_crash_the_loop(monkeypatch, tmp_path):
    _state(tmp_path, fail_streak="many", export_ts="yesterday", export_next_retry=None, export_fail_n="x", degraded_alert_ts="y", degraded_try_ts=[1],
           open={"a": "long ago"}, send_retry={"alert:a": {"n": "z", "next": "soon"}, "*": 5}, summary_day=7, fwd_err_first={"C1": "?"}, kis_rl={"calls_seen": "n"})
    st, sent = _loop(monkeypatch, tmp_path, 2, check=lambda now, wst=None: {"a": "stale"}, write_all=OK_EXPORT)
    assert "heartbeat" in st and st["fail_streak"] == 0 and sent[0] == "[watchdog] ISSUE a: stale" and len(sent) <= 2
    assert watch._int("7") == 0 and watch._int(True) == 0 and watch._num(float("nan"), 3) == 3 and watch._int(2.9) == 2


def test_send_budget_clock_starts_at_first_send(monkeypatch, tmp_path):
    clock = {"t": 1000.0}
    fake = types.SimpleNamespace(time=time.time, monotonic=lambda: clock["t"], sleep=time.sleep)
    monkeypatch.setattr(watch, "time", fake)
    calls = []

    def slow_check(now, wst=None):
        clock["t"] += 500                                      # a slow check/summary phase before any send must not eat the budget
        return {k: "x" for k in "abcd"}

    def send(m):
        calls.append(m)
        clock["t"] += 20
    st, _ = _loop(monkeypatch, tmp_path, 1, check=slow_check, write_all=OK_EXPORT, send=send)
    assert len(calls) == 3 and set(st["open"]) == {"a", "b", "c"}       # 0s, 20s, 40s are inside the 45 s budget; the 4th (60 s) waits for the next cycle


def test_summary_is_computed_only_when_a_send_is_allowed(monkeypatch, tmp_path):
    n = {"c": 0}
    monkeypatch.setattr(watch, "daily_summary", lambda now: n.__setitem__("c", n["c"] + 1) or "S")
    _state(tmp_path, send_retry={"*": {"n": 2, "next": time.time() + 600}})
    st, sent = _loop(monkeypatch, tmp_path, 3, write_all=OK_EXPORT, summary_hour=0)
    assert n["c"] == 0 and sent == [] and "summary_day" not in st                 # backing off: no computation, no send


def test_summary_catches_up_after_the_23h_window(monkeypatch, tmp_path):
    today = dt.datetime.now(UTC).strftime("%Y-%m-%d")
    monkeypatch.setattr(watch, "daily_summary", lambda now: "S")
    st, sent = _loop(monkeypatch, tmp_path, 1, write_all=OK_EXPORT)                # window closed (25) and nothing pending: no summary
    assert sent == []
    _state(tmp_path, summary_pending=today)                                        # failed earlier inside the window
    st, sent = _loop(monkeypatch, tmp_path, 1, write_all=OK_EXPORT)
    assert sent == ["S"] and st["summary_day"] == today and "summary_pending" not in st


def test_degraded_recovery_is_retried_until_delivered_and_try_ts_only_on_real_attempts(monkeypatch, tmp_path):
    ok = {"v": True}
    got = []

    def send(m):
        if not ok["v"]:
            return {"sent": False, "reason": "http 500"}
        got.append(m)

    def bad(now, wst=None):
        raise RuntimeError("x")
    _state(tmp_path, fail_streak=7, degraded_alert_ts=time.time() - 60)
    ok["v"] = False
    st, _ = _loop(monkeypatch, tmp_path, 1, write_all=OK_EXPORT, send=send)                  # healthy cycle, but Telegram is down
    assert st["degraded_recover_pending"] is True and st["degraded_alert_ts"]                # NOT popped until RECOVERED is delivered
    ok["v"] = True
    _rewind(tmp_path)
    st, _ = _loop(monkeypatch, tmp_path, 1, write_all=OK_EXPORT, send=send)
    assert got == ["[watchdog] RECOVERED watchdog_degraded"] and "degraded_alert_ts" not in st and "degraded_recover_pending" not in st
    _state(tmp_path, fail_streak=9, send_retry={"*": {"n": 1, "next": time.time() + 600}})   # degraded send is skipped (backoff): try_ts must stay unset
    st, _ = _loop(monkeypatch, tmp_path, 1, check=bad, write_all=OK_EXPORT, send=send)
    assert "degraded_try_ts" not in st


def test_forward_error_held_when_export_file_is_unusable(monkeypatch, tmp_path):
    _quiet(monkeypatch)
    rows = [{"candidate": "C3v", "status": "ERROR", "note": "ValueError: boom"}]
    wst = {}
    _fwd_file(tmp_path, monkeypatch, rows, NOW.timestamp())
    watch.check_all(NOW, wst)
    t = NOW + dt.timedelta(hours=3, minutes=5)
    _fwd_file(tmp_path, monkeypatch, rows, t.timestamp())
    assert "forward_error" in watch.check_all(t, wst)
    first = dict(wst["fwd_err_first"])
    p = tmp_path / "forward_status.json"
    for body in ("WITHHELD by the leak scan (secret-like pattern #1). Say that this information is unavailable.\n", "{not json",
                 json.dumps({"candidates": None}), json.dumps({"notice": "x"}), json.dumps(["a", "b"]), json.dumps({"candidates": "oops"}), ""):
        p.write_text(body)
        os.utime(p, (t.timestamp(), t.timestamp()))
        assert "forward_error" in watch.check_all(t, wst), body[:30]                         # previous result held: no false RECOVERED
        assert wst["fwd_err_first"] == first                                                   # no pruning, timers not reset
    p.unlink()
    assert "forward_error" in watch.check_all(t, wst)                                          # missing file holds too
    p.write_text(json.dumps({"candidates": [1, None, {"candidate": "C1", "status": "RUNNING"}]}))   # valid list without ERROR rows -> genuinely cleared
    os.utime(p, (t.timestamp(), t.timestamp()))
    assert "forward_error" not in watch.check_all(t, wst) and wst["fwd_err_first"] == {}


def test_gdelt_known_degraded_realerts_daily_other_issues_every_six_hours():
    known = "KNOWN DEGRADED gdelt (HTTP 429 rate limit, shared cooldown): 4/4 jobs affected"
    msgs, st = watch.diff_alerts({"gdelt_degraded": known, "other": "x"}, {}, 1000)
    assert len(msgs) == 2
    msgs, st = watch.diff_alerts({"gdelt_degraded": known, "other": "x"}, st, 1000 + watch.REALERT_S + 1)
    assert [m for m in msgs] == ["[watchdog] ISSUE other: x"]                                  # 6 h: only the ordinary issue repeats
    msgs, st = watch.diff_alerts({"gdelt_degraded": known, "other": "x"}, st, 1000 + 24 * 3600 + 1)
    assert any("gdelt_degraded" in m for m in msgs)                                             # 24 h: gdelt repeats
    failing = "gdelt jobs failing (not rate-limited): gdelt:a"
    msgs, st2 = watch.diff_alerts({"gdelt_degraded": failing}, {}, 1000)
    msgs, st2 = watch.diff_alerts({"gdelt_degraded": failing}, st2, 1000 + watch.REALERT_S + 1)
    assert len(msgs) == 1                                                                       # a real gdelt failure keeps the 6 h cadence
    msgs, st = watch.diff_alerts({}, st, 1000 + 24 * 3600 + 5)
    assert "[watchdog] RECOVERED gdelt_degraded" in msgs


def test_state_mem_dirty_then_clean(monkeypatch, tmp_path):
    monkeypatch.setattr(watch, "STATE", tmp_path / "watch_state.json")
    monkeypatch.setattr(watch, "_MEM", {})
    real = os.replace
    _broken_replace(monkeypatch)
    assert watch._save_state({"a": 1}) is False and watch._MEM["dirty"] is True and watch._load_state() == {"a": 1}
    monkeypatch.setattr(watch.os, "replace", real)
    assert watch._save_state({"a": 2}) is True and watch._MEM["dirty"] is False
    assert json.loads((tmp_path / "watch_state.json").read_text()) == {"a": 2} and watch._load_state() == {"a": 2}
    (tmp_path / "watch_state.json").write_text(json.dumps({"a": 3}))                         # clean: the file (not memory) is authoritative
    assert watch._load_state() == {"a": 3}
