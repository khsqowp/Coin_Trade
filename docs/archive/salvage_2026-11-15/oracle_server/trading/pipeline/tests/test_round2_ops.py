"""Round-2 operations + research helpers: scheduler slots / daily cap, watchdog alerts, retention, forward tracker, overlays."""
import datetime as dt
import json
import sqlite3

import numpy as np
import pandas as pd
import pytest

from helpers_ext import make_ohlcv
from tp import budget, forward, regime_det, research, retention, sched, watch

UTC = dt.timezone.utc


def T(s):
    return dt.datetime.strptime(s, "%Y-%m-%d %H:%M").replace(tzinfo=UTC)


# ------------------------------------------------------------------ scheduler
def test_crypto_slot_once_per_hour():
    now = T("2026-10-25 10:05")
    s = sched.due_slots(now, {})
    assert ("crypto", "20261025T10") in s
    assert not [x for x in sched.due_slots(now, {"crypto": "20261025T10"}) if x[0] == "crypto"]
    assert not sched.due_slots(T("2026-10-25 10:01"), {"crypto": "20261025T09"})   # minute < :02 not yet due


def test_kr_us_slots_catchup_window():
    s = dict(sched.due_slots(T("2026-10-25 23:40"), {"crypto": "20261025T23"}))
    assert s["kr"] == "20261025T2330"
    assert "kr" not in dict(sched.due_slots(T("2026-10-25 23:40"), {"crypto": "20261025T23", "kr": "20261025T2330"}))
    assert "kr" not in dict(sched.due_slots(T("2026-10-26 05:00"), {"crypto": "20261026T05"}))     # >3h after 23:30 and before 06:40
    assert dict(sched.due_slots(T("2026-10-26 06:41"), {"crypto": "20261026T06"}))["kr"] == "20261026T0640"
    assert dict(sched.due_slots(T("2026-10-25 12:35"), {"crypto": "20261025T12"}))["us"] == "20261025T1230"


def test_daily_cap_blocks_llm_but_not_other_days(tmp_path, monkeypatch):
    monkeypatch.setattr(budget, "LEDGER", tmp_path / "l.jsonl")
    monkeypatch.setattr(budget, "DAILY_CAP", 0.30)
    monkeypatch.setattr(budget, "BUDGET_BASELINE", 0.0)
    budget.record(run_id="sched-crypto-1", cost=0.2, ts="2026-10-24T01:00:00Z")      # other day: ignored
    budget.record(run_id="sched-crypto-2", cost=0.2)
    budget.record(run_id="manual-1", cost=0.5)                                       # non-scheduler spend does not count toward the daily cap
    assert budget.sched_spent_today() == pytest.approx(0.2)
    budget.check()
    budget.record(run_id="sched-kr-1", cost=0.15)
    with pytest.raises(budget.DailyCapExceeded):
        budget.check()


def test_daily_cap_zero_means_disabled(tmp_path, monkeypatch):
    monkeypatch.setattr(budget, "LEDGER", tmp_path / "l.jsonl")
    monkeypatch.setattr(budget, "DAILY_CAP", 0.0)
    monkeypatch.setattr(budget, "BUDGET_BASELINE", 0.0)
    budget.record(run_id="sched-x", cost=5.0 if False else 0.5)
    budget.check()


# ------------------------------------------------------------------ watchdog
def test_diff_alerts_lifecycle():
    st = {}
    m, st = watch.diff_alerts({"a": "stale"}, st, 1000)
    assert len(m) == 1 and "ISSUE a" in m[0]
    m, st = watch.diff_alerts({"a": "stale"}, st, 1100)
    assert m == []                                            # no spam
    m, st = watch.diff_alerts({"a": "stale"}, st, 1000 + watch.REALERT_S + 1)
    assert len(m) == 1                                        # re-alert
    m, st = watch.diff_alerts({}, st, 1000 + watch.REALERT_S + 5)
    assert m == ["[watchdog] RECOVERED a"] and st["open"] == {}


# ------------------------------------------------------------------ retention
def test_prune_news_only_touches_fetch_log():
    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE fetch_log(at TEXT, job TEXT, url TEXT, ok INT, http INT, n_new INT, note TEXT)")
    con.execute("CREATE TABLE items(id INTEGER)")
    con.execute("INSERT INTO items VALUES (1)")
    now = T("2026-10-25 00:00")
    con.execute("INSERT INTO fetch_log VALUES ('2026-06-01T00:00:00Z','j','u',1,200,0,'')")
    con.execute("INSERT INTO fetch_log VALUES ('2026-10-20T00:00:00Z','j','u',1,200,0,'')")
    assert retention.prune_news(con, now)["fetch_log_deleted"] == 1
    assert con.execute("SELECT COUNT(*) FROM fetch_log").fetchone()[0] == 1
    assert con.execute("SELECT COUNT(*) FROM items").fetchone()[0] == 1


def test_thin_hl_keeps_one_per_hour_and_recent():
    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE positions(snap_ts TEXT, addr TEXT, coin TEXT, v REAL)")
    for mnt in range(0, 60, 10):                                   # 6 old snapshots in one hour
        con.execute("INSERT INTO positions VALUES (?,?,?,?)", ("2026-08-01T10:%02d:00Z" % mnt, "a", "BTC", 1.0))
    con.execute("INSERT INTO positions VALUES ('2026-10-24T10:00:00Z','a','BTC',1.0)")
    con.execute("INSERT INTO positions VALUES ('2026-10-24T10:10:00Z','a','BTC',1.0)")
    retention.thin_hl(con, T("2026-10-25 00:00"))
    assert con.execute("SELECT COUNT(*) FROM positions WHERE snap_ts<'2026-09-01'").fetchone()[0] == 1
    assert con.execute("SELECT COUNT(*) FROM positions WHERE snap_ts>'2026-10-01'").fetchone()[0] == 2


# ------------------------------------------------------------------ deterministic regime + research helpers
def test_regime_det_labels_and_causality():
    df = make_ohlcv(1200, drift=0.002, vol=0.004, freq="4h")
    lab = regime_det.classify_series(df)
    assert set(lab.unique()) <= {"trend_up", "trend_down", "range", "high_vol", "unknown"}
    assert (lab.iloc[-300:] == "trend_up").mean() > 0.5
    cut = df.iloc[:900]
    pd.testing.assert_series_equal(regime_det.classify_series(cut), lab.iloc[:900], check_names=False)   # no look-ahead


def test_align_is_causal():
    h = pd.date_range("2026-01-01", periods=8, freq="1h", tz="UTC")
    sig = pd.Series(np.arange(1.0, 9.0), index=h)                     # value known at the CLOSE of that hour
    clock = pd.date_range("2026-01-01", periods=16, freq="15min", tz="UTC")
    a = research.align(sig, "1h", clock, "15m")
    assert a[0] == 0 and a[1] == 0 and a[2] == 0                       # 1h bar 0 closes at 01:00 = close of clock bar 3
    assert a[3] == 1.0 and a[6] == 1.0 and a[7] == 2.0


def test_vol_scale_bounds_and_fomc_mask_and_a1():
    df = make_ohlcv(3000, vol=0.004)
    vs = research.vol_scale(df, "1h")
    assert vs.min() >= 0.25 and vs.max() <= 2.0 and np.allclose(vs * 4, np.round(vs * 4))
    ev = [df.index[1000].to_pydatetime() + dt.timedelta(hours=1)]
    m = research.fomc_mask(df, "1h", ev, hours=6)
    assert 11 <= m.sum() <= 14 and m[1000]
    labs = np.array(["trend_up", "trend_down", "range", "high_vol", "unknown"], dtype=object)
    one = np.ones(5)
    cfg = {(st, side, tf): one for st, side, tf, _w in research.A1_TABLE.values()}
    out = research.a1_signal(labs, cfg)
    assert out[4] == 0 and out[0] == 1.0 and abs(out).max() <= 1.0


def test_dsr_penalises_more_trials():
    rng = np.random.RandomState(1)
    r = rng.normal(0.0002, 0.01, 24 * 365)
    few = research.dsr_ann(r, 24 * 365, rng.normal(0.3, 0.3, 5))
    many = research.dsr_ann(r, 24 * 365, rng.normal(0.3, 0.3, 500))
    assert many[1] > few[1] and many[0] <= few[0]


# ------------------------------------------------------------------ forward tracker
@pytest.fixture()
def fwd(tmp_path, monkeypatch):
    df = make_ohlcv(2000, drift=0.0003)
    monkeypatch.setattr(forward, "REG", tmp_path / "reg.json")
    monkeypatch.setattr(research, "load_df", lambda sym, tf: df)
    monkeypatch.setattr(research, "fund_arr", lambda sym, d, tf: np.zeros(len(d)))
    return df


def test_registry_is_create_once(fwd):
    r1 = forward.registry(T("2026-10-25 00:00"))
    r2 = forward.registry(T("2026-12-01 00:00"))
    assert r1 == r2 and set(r1) == set(forward.CANDIDATES)


def test_forward_eval_starts_flat_after_registration(fwd):
    reg = {k: fwd.index[1500].strftime("%Y-%m-%dT%H:%M:%SZ") for k in forward.CANDIDATES}
    r = forward.evaluate("C0_buyhold_BTC", reg)
    assert r["bars"] == 500 and r["status"] == "BENCHMARK" and r["trades"] == 1
    assert r["days"] == pytest.approx(500 / 24, abs=0.1)
    future = {k: (fwd.index[-1] + pd.Timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ") for k in forward.CANDIDATES}
    assert forward.evaluate("C0_buyhold_BTC", future)["status"] == "RUNNING"


def test_forward_overlay_candidate_runs(fwd, monkeypatch):
    monkeypatch.setattr(research, "get_signal", lambda st, side, sym, tf, df=None: pd.Series(np.where(np.arange(len(fwd)) % 200 < 100, 1.0, -1.0), index=fwd.index))
    reg = {k: fwd.index[1000].strftime("%Y-%m-%dT%H:%M:%SZ") for k in forward.CANDIDATES}
    for k in ("C3_trend_mtf_ls_BTC_1h", "C3v_voltarget", "C3r_retire"):
        r = forward.evaluate(k, reg)
        assert r["bars"] == 1000 and r["trades"] >= 4 and "status" in r


def test_judge_pre_registered_rules():
    j = forward.judge
    assert j("single", 10, 30, 3.0, 0.05, 0.1) == "RUNNING"                 # too short
    assert j("single", 40, 5, 3.0, 0.05, 0.1) == "RUNNING"                  # too few trades
    assert j("single", 40, 30, 0.8, 0.10, 0.05) == "SUCCESS"
    assert j("single", 40, 30, 0.8, 0.17, 0.05) == "INCONCLUSIVE"           # mdd between 15% and 20%
    assert j("single", 40, 30, -0.2, 0.10, -0.02) == "FAIL (sharpe<0)"
    assert j("single", 10, 3, 1.0, 0.25, -0.1) == "FAIL (mdd)"              # early fail on drawdown
    assert j("bh", 40, 1, 1.0, 0.5, 0.1) == "BENCHMARK"


# ------------------------------------------------------------------ time zones (storage UTC, display / session logic explicit IANA)
def test_kr_session_uses_explicit_seoul_zone(monkeypatch):
    from tp import kisintra
    monkeypatch.setenv("TZ", "America/Los_Angeles")           # host/container TZ must not matter
    import time as _t
    _t.tzset()
    try:
        utc = dt.datetime(2026, 10, 26, 0, 10, tzinfo=UTC)    # Monday 09:10 KST
        assert kisintra.in_session(utc.astimezone(kisintra.KST))
        assert not kisintra.in_session(dt.datetime(2026, 10, 26, 6, 40, tzinfo=UTC).astimezone(kisintra.KST))   # 15:40 KST
        assert not kisintra.in_session(dt.datetime(2026, 10, 25, 0, 10, tzinfo=UTC).astimezone(kisintra.KST))   # Sunday
    finally:
        monkeypatch.delenv("TZ")
        _t.tzset()


def test_us_close_dst_boundaries():
    from tp import news
    d = dt.date(2026, 7, 1)                                    # EDT: close 20:00 UTC, complete from 20:30 UTC
    assert not news._et_close_passed(d, dt.datetime(2026, 7, 1, 20, 29, tzinfo=UTC))
    assert news._et_close_passed(d, dt.datetime(2026, 7, 1, 20, 30, tzinfo=UTC))
    w = dt.date(2026, 12, 1)                                   # EST: close 21:00 UTC, complete from 21:30 UTC
    assert not news._et_close_passed(w, dt.datetime(2026, 12, 1, 21, 29, tzinfo=UTC))
    assert news._et_close_passed(w, dt.datetime(2026, 12, 1, 21, 30, tzinfo=UTC))
    for day in (dt.date(2026, 11, 2), dt.date(2026, 3, 9)):     # day after the DST switches (Nov 1 / Mar 8)
        edge = dt.datetime.combine(day, dt.time(16, 30), tzinfo=__import__("zoneinfo").ZoneInfo("America/New_York")).astimezone(UTC)
        assert news._et_close_passed(day, edge) and not news._et_close_passed(day, edge - dt.timedelta(minutes=1))


def test_budget_day_is_kst_midnight_and_never_undercounts(tmp_path, monkeypatch):
    assert budget.day_start_utc(T("2026-10-25 04:00")) == "2026-10-24T15:00:00Z"      # 13:00 KST -> KST midnight
    assert budget.day_start_utc(T("2026-10-25 16:00")) == "2026-10-25T15:00:00Z"      # 01:00 KST next day
    monkeypatch.setattr(budget, "LEDGER", tmp_path / "l.jsonl")
    budget.record(run_id="sched-a", cost=0.1, ts="2026-10-24T14:59:59Z")              # before KST midnight: previous day
    budget.record(run_id="sched-b", cost=0.2, ts="2026-10-24T15:00:00Z")              # inside today's KST day (yesterday UTC)
    budget.record(run_id="sched-c", cost=0.3, ts="2026-10-25T03:00:00Z")
    assert budget.sched_spent_today(T("2026-10-25 04:00")) == pytest.approx(0.5)
