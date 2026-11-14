"""Watchdog + daily Telegram summary. NO LLM. Runs in container `tp-watch` (Telegram vars only, data read-only, runs rw).

Checks every 60 s (heartbeat ages, per-collector freshness, KIS during the KR session, disk, budget) and alerts once per issue
(re-alert after 6 h; a recovery message when it clears). Daily summary at 23:00 UTC (08:00 KST). Every outgoing text passes the
notify secret scrubber. The watchdog never deletes anything and never restarts anything (restart policy handles crashes)."""
import datetime as dt
import json
import os
import shutil
import sqlite3
import time
import traceback

from . import budget, config, deriv, hl, kisintra, news, notify
from .config import DATA, RUNS, scrub

STATE = RUNS / "watch_state.json"
SUMMARY_HOUR_UTC = 23
REALERT_S = 6 * 3600
EXPORT_EVERY_S = 1800
EXPORT_RETRY_S = (300, 600, 1200, 1800)       # backoff after a failed export: 5m, 10m, 20m, then capped at 30m
KIS_RL_MIN_CALLS, KIS_RL_SET_PCT, KIS_RL_CLEAR_PCT = 200, 25, 10     # set when limited > 25% of calls (total >= 200), clear below 10%
DEGRADED_AFTER, EXPORT_FAIL_N, EXPORT_STALE_S = 5, 3, 7200


def err_record(e, where):
    """Structured, scrubbed error record for watch_state.json: {at, where, type, msg<=200, tb_tail = last 3 pipeline (/tp/) frames file:line:func}.
    Built defensively: a failing str(e) / traceback walk must never kill the watch loop."""
    at = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        frames = traceback.extract_tb(e.__traceback__)
        mine = [f for f in frames if "/tp/" in f.filename.replace("\\", "/")]
        tail = [scrub("%s:%s:%s" % (os.path.basename(f.filename), f.lineno, f.name), 80) for f in (mine or frames)[-3:]]
        return {"at": at, "where": str(where)[:40], "type": type(e).__name__, "msg": scrub(e, 200), "tb_tail": tail}
    except Exception:       # noqa: BLE001
        return {"at": at, "where": "err_record", "type": "unknown", "msg": "error record unavailable", "tb_tail": []}


def resolve_last_error(st, now, keep_budget_policy=True):
    """Called after a fully successful cycle: last_error -> None, keep the resolved record (last_error_last) and last_error_resolved_at.
    A budget_policy error (that stage runs once a day) is NOT resolved by unrelated cycles, only by the next daily attempt (keep_budget_policy=False)."""
    prev = st.get("last_error")
    if prev and keep_budget_policy and isinstance(prev, dict) and prev.get("where") == "budget_policy":
        return
    if prev:
        ts = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        st["last_error_last"] = dict(prev, resolved_at=ts) if isinstance(prev, dict) else {"msg": scrub(prev, 200)}
        st["last_error_resolved_at"] = ts
    st["last_error"] = None


def export_backoff(n_fail):
    return EXPORT_RETRY_S[min(max(n_fail, 1), len(EXPORT_RETRY_S)) - 1]


KIS_ACTIVE_STATES = ("collecting", "sleeping_between_cycles")


def kis_ratelimit_issue(k, now, wst=None):
    """Sustained KIS pacing pressure (informational: a pacing issue, not a hard quota). Source: collector status.json keys state, last_cycle.at,
    calls_today, rate_limited_today (EGW00201 per-second responses), errors_today and last_error.msg.
    Counters are evaluated ONLY while the collector is in an active state AND a cycle completed today (KST) at/after the open; otherwise the
    previous day's counters (kept until the first call of a day) could leak in. Hysteresis kept in wst["kis_rl"]: set when lim*100 > total*25
    (total >= 200), cleared when lim*100 < total*10; an exhausted-retries error (errors_today grows with last_error 'retries exhausted') sets it
    at once. Not evaluable (out of session, weekend, holiday): the previous state is held silently (wst["kis_rl"]["hold"]) - no RECOVERED."""
    wst = {} if wst is None else wst
    rl = wst.setdefault("kis_rl", {})
    kst = now.astimezone(kisintra.KST)
    today = kst.date().isoformat()
    try:
        lc = dt.datetime.fromisoformat(str((k.get("last_cycle") or {}).get("at"))).astimezone(kisintra.KST)
        evaluable = (k.get("state") in KIS_ACTIVE_STATES and kst.weekday() < 5 and lc.date() == kst.date() and lc.time() >= kisintra.OPEN
                     and kst.time() >= kisintra.OPEN)
        total, lim, errs = int(k.get("calls_today") or 0), int(k.get("rate_limited_today") or 0), int(k.get("errors_today") or 0)
    except (ValueError, TypeError):
        evaluable = False
    if not evaluable:
        rl["hold"] = bool(rl.get("active"))
        return rl.get("msg") if rl.get("active") else None
    rl["hold"] = False
    if rl.get("day") != today:                      # new KST day: counters were reset by the collector
        if rl.get("active"):
            wst.get("open", {}).pop("kis_ratelimit", None)      # silent reset (no RECOVERED for a day rollover)
        base = errs if rl.get("day") is None else 0
        rl.update(day=today, active=False, msg=None, errors_seen=base)
    exhausted = errs > int(rl.get("errors_seen", 0)) and "retries exhausted" in str((k.get("last_error") or {}).get("msg", ""))
    rl["errors_seen"] = errs
    if total >= KIS_RL_MIN_CALLS and lim * 100 < total * KIS_RL_CLEAR_PCT:
        rl.update(active=False, msg=None)
    if exhausted:
        rl.update(active=True, msg="KIS pacing (informational, not a hard quota): collector reported retries exhausted, errors_today=%d, "
                                   "rate-limited %d of %d calls (KST %s)" % (errs, lim, total, today))
    elif total >= KIS_RL_MIN_CALLS and lim * 100 > total * KIS_RL_SET_PCT:
        rl.update(active=True, msg="KIS pacing (informational, not a hard quota): %d of %d API calls rate-limited today (KST %s) = %.1f%%, "
                                   "sustained above %d%%" % (lim, total, today, 100.0 * lim / total, KIS_RL_SET_PCT))
    return rl.get("msg") if rl.get("active") else None


def _age(iso_s, now):
    try:
        t = dt.datetime.fromisoformat(str(iso_s).replace("Z", "+00:00"))
        if t.tzinfo is None:
            t = t.replace(tzinfo=dt.timezone.utc)
        return (now - t).total_seconds()
    except (ValueError, TypeError):
        return 1e9


def _load(p):
    try:
        return json.loads(p.read_text())
    except (OSError, ValueError):
        return None


def gdelt_issue(jobs, now):
    """ONE aggregated message for all gdelt jobs. A shared 429 cooldown is reported as a KNOWN DEGRADED source (still visible,
    re-alerted every REALERT_S, RECOVERED when it clears) instead of one open issue per job."""
    gj = {k: j for k, j in jobs.items() if k.startswith("gdelt")}
    if not gj:
        return None
    cd = news.cooldown_state()
    left = max(0.0, float(cd.get("until", 0)) - now.timestamp())
    bad = sorted(k for k, j in gj.items() if j.get("fails", 0) >= 3)
    oks = [j["last_ok"] for j in gj.values() if j.get("last_ok")]
    last_ok = max(oks) if oks else None
    if left > 0 or int(cd.get("consec", 0)) >= 1:
        return "KNOWN DEGRADED gdelt (HTTP 429 rate limit, shared cooldown): %d/%d jobs affected, consecutive 429=%s, cooldown %.1fh left, last_ok=%s" % (
            len(bad) or len(gj), len(gj), cd.get("consec"), left / 3600, last_ok)
    if bad:
        return "gdelt jobs failing (not rate-limited): %s; last_ok=%s err=%s" % (",".join(bad), last_ok, gj[bad[0]].get("last_err"))
    if last_ok and _age(last_ok, now) > 6 * 3600 * 2:
        return "gdelt no successful fetch for %.0fh (last_ok=%s)" % (_age(last_ok, now) / 3600, last_ok)
    return None


def check_all(now=None, wst=None):
    """Return {issue_key: message}. Pure function of the status files / DBs (testable)."""
    now = now or dt.datetime.now(dt.timezone.utc)
    wst = {} if wst is None else wst
    iss = {}
    s = _load(news.STATUS)
    if not s or _age(s.get("updated"), now) > 180:
        iss["news_heartbeat"] = "news collector heartbeat stale/missing"
    else:
        for k, j in s.get("jobs", {}).items():
            if k.startswith("gdelt"):
                continue                # aggregated below (known rate-limited source), not one issue per job
            lim = {"gdelt": 10800, "fng": 30000, "us_daily": 30000, "parquet_export": 7200, "retention": 100000}.get(k.split(":")[0], 2400)
            if j.get("fails", 0) >= (8 if k.startswith("gdelt") else 3) or (j.get("last_ok") and _age(j["last_ok"], now) > lim and not k.startswith("gdelt")):
                iss["news_job_" + k] = "news job %s fails=%s last_ok=%s err=%s" % (k, j.get("fails"), j.get("last_ok"), j.get("last_err"))
        g = gdelt_issue(s.get("jobs", {}), now)
        if g:
            iss["gdelt_degraded"] = g
    k = _load(kisintra.STATUS)
    kst = now.astimezone(kisintra.KST)
    if not k or _age(k.get("heartbeat"), now) > 180:
        iss["kis_heartbeat"] = "KIS collector heartbeat stale/missing"
    elif kisintra.in_session(kst) and kst.time() >= (dt.datetime.combine(kst.date(), dt.time(9, 20))).time() and k.get("state") not in ("no_data_today(holiday?)",):
        lc = (k.get("last_cycle") or {}).get("at")
        if not lc or _age(lc, now) > 900:
            iss["kis_stale"] = "KIS in session but last collection cycle %s" % (lc or "never")
        if k.get("state") in ("error_backoff", "stopped_daily_cap"):
            iss["kis_state"] = "KIS collector state=%s err=%s" % (k.get("state"), (k.get("last_error") or {}).get("msg"))
    if k and _age(k.get("heartbeat"), now) <= 180:
        rl = kis_ratelimit_issue(k, now, wst)
        if rl:
            iss["kis_ratelimit"] = rl
    ets = wst.get("export_ts")
    if int(wst.get("export_fail_n", 0)) >= EXPORT_FAIL_N or (ets and now.timestamp() - ets > EXPORT_STALE_S):
        iss["export_failing"] = "hermes export failing: %s consecutive failures, last success %s, last error %s" % (
            wst.get("export_fail_n", 0), dt.datetime.fromtimestamp(ets, dt.timezone.utc).strftime("%Y-%m-%dT%H:%MZ") if ets else "never",
            (wst.get("export_error") or {}).get("type") if isinstance(wst.get("export_error"), dict) else None)
    d = _load(deriv.STATUS)
    if not d or _age(d.get("updated"), now) > 120:
        iss["deriv_heartbeat"] = "derivatives collector heartbeat stale/missing"
    else:
        if _age((d.get("ws") or {}).get("heartbeat"), now) > 300:
            iss["deriv_ws"] = "Binance liquidation stream silent > 5 min"
        if d.get("rest") and any(_age(v.get("last_ok"), now) > 2400 for v in d["rest"].values()):
            iss["deriv_rest"] = "Binance OI/long-short polling stale > 40 min"
    h = _load(hl.STATUS)
    if not h or _age(h.get("updated"), now) > 120:
        iss["hl_heartbeat"] = "Hyperliquid collector heartbeat stale/missing"
    else:
        if _age((h.get("ws") or {}).get("heartbeat"), now) > 300:
            iss["hl_ws"] = "Hyperliquid trades stream silent > 5 min"
        if _age((h.get("poll") or {}).get("last_ok"), now) > 900:
            iss["hl_poll"] = "Hyperliquid position polling stale > 15 min"
    sc = _load(RUNS / "sched_status.json")
    if sc is not None and sc.get("enabled", True) and _age(sc.get("heartbeat"), now) > 180:
        iss["sched_heartbeat"] = "scheduler heartbeat stale"
    du = shutil.disk_usage(DATA)
    free = du.free / du.total
    if free < 0.10:
        iss["disk_critical"] = "disk free %.0f%%" % (free * 100)
    elif free < 0.20:
        iss["disk_low"] = "disk free %.0f%%" % (free * 100)
    spent = budget.task_spent()
    if spent >= 0.6 * config.BUDGET_TOTAL:
        iss["budget_60"] = "LLM budget %.0f%% used ($%.2f of $%.2f; auto-stop at 80%%)" % (100 * spent / config.BUDGET_TOTAL, spent, config.BUDGET_TOTAL)
    return iss


def diff_alerts_keyed(issues, state, now_ts):
    """Return ([(key, kind, message)], new_state). kind: ISSUE | RECOVERED. Alert on new issues, re-alert after REALERT_S, announce recoveries.
    A held issue (kis_rl.hold: not evaluable, previous state kept) stays open silently: no re-alert, no RECOVERED."""
    open_ = state.get("open", {})
    held = bool((state.get("kis_rl") or {}).get("hold"))
    out, new_open = [], {}
    for k, m in issues.items():
        last = open_.get(k)
        if k == "kis_ratelimit" and held and last is not None:
            new_open[k] = last
        elif last is None or now_ts - last >= REALERT_S:
            out.append((k, "ISSUE", "[watchdog] ISSUE %s: %s" % (k, m)))
            new_open[k] = now_ts
        else:
            new_open[k] = last
    for k in open_:
        if k not in issues:
            out.append((k, "RECOVERED", "[watchdog] RECOVERED %s" % k))
    return out, dict(state, open=new_open)


def diff_alerts(issues, state, now_ts):
    """Compatibility wrapper: (messages, new_state)."""
    out, new = diff_alerts_keyed(issues, state, now_ts)
    return [m for _k, _t, m in out], new


def _count(path, q, args=()):
    try:
        c = sqlite3.connect("file:%s?mode=ro" % path, uri=True, timeout=10)
        r = c.execute(q, args).fetchone()
        c.close()
        return r
    except Exception:       # noqa: BLE001
        return None


def daily_summary(now=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    t24 = (now - dt.timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ")
    ms24 = int((now - dt.timedelta(hours=24)).timestamp() * 1000)
    L = ["[daily] %s KST (+09:00); 저장 시각은 UTC" % now.astimezone(kisintra.KST).strftime("%Y-%m-%d %H:%M")]
    c = _count(news.DB, "SELECT COUNT(*) FROM items WHERE fetched_at>=?", (t24,))
    f = _count(news.DB, "SELECT COUNT(*) FROM features WHERE fetched_at>=?", (t24,))
    L.append("수집 24h: 뉴스 %s건, 피처 %s건" % (c and c[0], f and f[0]))
    k = _load(kisintra.STATUS) or {}
    days = sorted(p.name for p in (kisintra.KR_DIR).glob("2*") if p.is_dir()) if kisintra.KR_DIR.exists() else []
    L.append("KIS 분봉: 저장 세션 %d일(최근 %s), 상태 %s" % (len(days), days[-1] if days else "-", k.get("state")))
    lq = _count(deriv.DB, "SELECT COUNT(*) FROM liq WHERE ts_ms>=?", (ms24,))
    oi = _count(deriv.DB, "SELECT COUNT(*), MAX(ts_ms) FROM oi_hist")
    L.append("Binance 파생: 강제청산 %s건/24h, OI 누적 %s" % (lq and lq[0], oi and oi[0]))
    hp = _count(hl.DB, "SELECT COUNT(*) FROM positions WHERE snap_ts>=?", (t24,))
    ha = _count(hl.DB, "SELECT COUNT(*), SUM(has_pos) FROM addrs")
    L.append("Hyperliquid: 주소 %s(보유 %s), 포지션 스냅샷 %s건/24h" % (ha and ha[0], ha and ha[1], hp and hp[0]))
    iss = check_all(now)
    L.append("이상 감지: %s" % ("없음" if not iss else "; ".join("%s" % m for m in list(iss.values())[:4])))
    sc = _load(RUNS / "sched_status.json") or {}
    L.append("예산: 이번 라운드 $%.3f / $%.2f (80%% 정지 $%.2f), 스케줄러 오늘 $%.3f / $%.2f, 실행 %s건(carry %s, 한도스킵 %s, 오류 %s)" % (
        budget.task_spent(), config.BUDGET_TOTAL, 0.8 * config.BUDGET_TOTAL, budget.sched_spent_today(), config.DAILY_CAP or 0.30,
        sc.get("runs"), sc.get("carried"), sc.get("skipped_daily_cap"), sc.get("errors")))
    try:
        from . import regime
        con = regime.log_con()
        for m in ("crypto", "kr", "us"):
            r = con.execute("SELECT asof, output_json, status, source FROM regime_log WHERE market=? ORDER BY id DESC LIMIT 1", (m,)).fetchone()
            if r:
                o = json.loads(r[1])
                L.append("국면 %s: %s conf %.2f event %s 위험배율 %.2f (%s/%s %s)" % (m, o["regime"], o["confidence"], o["event_risk"],
                                                                                o["risk_multiplier"], r[3], r[2], r[0][5:16] + "Z"))
        n = con.execute("SELECT COUNT(*) FROM regime_log").fetchone()[0]
        L.append("국면 로그 %d행, 해시체인 %s" % (n, "OK" if regime.verify_chain(con) else "BROKEN"))
        con.close()
    except Exception as e:      # noqa: BLE001
        L.append("국면 로그 읽기 실패: %s" % type(e).__name__)
    try:
        from . import forward
        rows = forward.evaluate_all(now)
        L.append(forward.summary_line(rows))
        for r in rows:
            if r.get("status", "").startswith(("SUCCESS", "FAIL")):
                L.append("  %s %s ret %.1f%% sharpe %.2f mdd %.1f%%" % (r["candidate"], r["status"], 100 * r["total_return"], r["sharpe"], 100 * r["mdd"]))
    except Exception as e:      # noqa: BLE001
        L.append("forward 평가 실패: %s" % type(e).__name__)
    try:
        from . import budget_policy
        L.append(budget_policy.summary_line(budget_policy.check(now)))
    except Exception as e:      # noqa: BLE001
        L.append("예산 정책 평가 실패: %s" % type(e).__name__)
    du = shutil.disk_usage(DATA)
    L.append("디스크 여유 %.0f%% (%.0fGB), data %s" % (100 * du.free / du.total, du.free / 1e9, _dirsize(DATA)))
    return "\n".join(L)


def _dirsize(p):
    tot = 0
    for f in p.rglob("*"):
        try:
            if f.is_file():
                tot += f.stat().st_size
        except OSError:
            pass
    return "%.0fMB" % (tot / 1e6)


def _delivered(res):
    """notify.send never raises: it returns {'sent': bool, ...}. Test doubles return None (= delivered)."""
    return res.get("sent") is True if isinstance(res, dict) else (res is None or bool(res))


def _save_state(st):
    """Atomic write (tmp + os.replace); a failing write must not kill the loop or leave a truncated state file."""
    tmp = STATE.with_name(STATE.name + ".tmp")
    try:
        tmp.write_text(json.dumps(st, indent=1))
        os.replace(tmp, STATE)
    except Exception:       # noqa: BLE001
        try:
            tmp.unlink()
        except OSError:
            pass


def _deliver(send, out, state, prev_open):
    """Send keyed alerts; mark an alert as sent only if it was delivered (otherwise it stays pending and is retried next cycle)."""
    failed = 0
    for key, kind, msg in out:
        try:
            ok = _delivered(send(scrub(msg, 600)))
        except Exception:       # noqa: BLE001
            ok = False
        if not ok:
            failed += 1
            if kind == "ISSUE" and key not in prev_open:
                state["open"].pop(key, None)
            elif kind == "ISSUE":
                state["open"][key] = prev_open[key]
            else:
                state["open"][key] = prev_open[key]
    return failed


def run_forever(stop=lambda: False, sleep=time.sleep, send=None):
    send = send or (lambda t: notify.send(t))
    while not stop():
        now = dt.datetime.now(dt.timezone.utc)
        st = _load(STATE) or {}
        ok, stage, bp_ok = True, "load", False
        try:
            stage = "check_all"
            issues = check_all(now, st)
            stage = "diff_alerts"
            prev_open = dict(st.get("open", {}))
            out, st = diff_alerts_keyed(issues, st, time.time())
            stage = "send_alerts"
            if _deliver(send, out, st, prev_open):      # undelivered alerts stay pending (retried next cycle); the rest of the cycle still runs
                ok = False
                st["last_error"] = err_record(RuntimeError("alert delivery failed; pending alerts retried next cycle"), "send_alerts")
            day = now.strftime("%Y-%m-%d")
            if now.hour >= SUMMARY_HOUR_UTC and st.get("summary_day") != day:
                stage = "daily_summary"
                send(daily_summary(now))
                st["summary_day"] = day
                stage = "budget_policy"
                try:      # budget-increase PROPOSAL only (deterministic); the cap itself is changed solely by the owner on the host
                    from . import budget_policy
                    txt, _d = budget_policy.propose(now)
                    if txt:
                        send(scrub(txt, 900))
                    bp_ok = True
                except Exception as e:      # noqa: BLE001
                    ok = False
                    st["last_error"] = err_record(e, "budget_policy")
            stage = "export"
            t = time.time()
            if t - st.get("export_ts", 0) >= EXPORT_EVERY_S and t >= st.get("export_next_retry", 0):
                try:
                    from . import hermesx
                    rep = hermesx.write_all(now)
                    st["export_ts"], st["export_withheld"] = time.time(), rep["withheld"]
                    st.pop("export_next_retry", None)
                    st["export_fail_n"], st["export_error"] = 0, None
                except Exception as e:      # noqa: BLE001  export_ts is NOT advanced: retry with backoff instead of waiting EXPORT_EVERY_S
                    n = int(st.get("export_fail_n", 0)) + 1
                    st["export_fail_n"] = n
                    st["export_next_retry"] = time.time() + export_backoff(n)
                    st["export_error"] = err_record(e, "export")
            st["heartbeat"] = now.isoformat()
        except Exception as e:      # noqa: BLE001
            ok = False
            st["last_error"] = err_record(e, stage)
        if ok:
            st["fail_streak"] = 0
            resolve_last_error(st, now, keep_budget_policy=not bp_ok)
            if st.pop("degraded_alert_ts", None):
                try:
                    send("[watchdog] RECOVERED watchdog_degraded")
                except Exception:       # noqa: BLE001
                    pass
        else:
            st["fail_streak"] = int(st.get("fail_streak", 0)) + 1
            if st["fail_streak"] >= DEGRADED_AFTER and time.time() - st.get("degraded_alert_ts", 0) >= REALERT_S:
                le = st.get("last_error") if isinstance(st.get("last_error"), dict) else {}
                try:
                    if _delivered(send("[watchdog] ISSUE watchdog_degraded: %d consecutive failed cycles; last error where=%s type=%s" % (
                            st["fail_streak"], le.get("where"), le.get("type")))):
                        st["degraded_alert_ts"] = time.time()
                except Exception:       # noqa: BLE001
                    pass
        _save_state(st)
        sleep(60)
