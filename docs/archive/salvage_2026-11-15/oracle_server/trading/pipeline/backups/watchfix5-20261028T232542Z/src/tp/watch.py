"""Watchdog + daily Telegram summary. NO LLM. Runs in container `tp-watch` (Telegram vars only, data read-only, runs rw).

Checks every 60 s (heartbeat ages, per-collector freshness, KIS during the KR session, disk, budget) and alerts once per issue
(re-alert after 6 h; a recovery message when it clears). Daily summary at 23:00 UTC (08:00 KST). Every outgoing text passes the
notify secret scrubber. The watchdog never deletes anything and never restarts anything (restart policy handles crashes)."""
import datetime as dt
import copy
import json
import math
import os
import re
import shutil
import sqlite3
import sys
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
DEGRADED_TRY_S = 900                        # min gap between attempts to send "watchdog_degraded" (separate from the 6 h REALERT_S)
SEND_BUDGET_S = 45                          # max wall time spent sending in one cycle
SEND_BACKOFF_S, SEND_BACKOFF_MAX_S = 60, 900    # per-key retry backoff after a failed send: 1, 2, 4 ... 15 min
KIS_EX_EVENTS, KIS_EX_WINDOW_S, KIS_EX_CLEAR_S = 3, 1800, 3600    # retries-exhausted latch: 3 events within 30 min; clears after 60 min quiet
FWD_ERR_AFTER_S = 3 * 3600
REALERT_GDELT_S = 24 * 3600                 # KNOWN DEGRADED gdelt (shared HTTP 429 cooldown) is a long-lived known state: re-alert daily, not every 6 h
CLIENT_DROP_AFTER = 5                       # HTTP 4xx (not 429): back off only that key, drop the message after this many attempts
PROPOSAL_MAX_AGE_S = 3 * 86400
NO_TELEGRAM = ("telegram_disabled",)        # status-only issues: shown in the summary / Hermes export, never sent to Telegram
CONSUMED = ("sent", "disabled", "dropped")
_TG_LOGGED = {"v": False}                   # "Telegram not configured" is logged once per PROCESS (in memory only, never persisted)
_MEM = {}                                   # in-memory copy of the watch state (source of truth while the state file cannot be written)


def _log(msg):
    try:
        sys.stderr.write("[watch] %s\n" % scrub(msg, 300))
        sys.stderr.flush()
    except Exception:       # noqa: BLE001
        pass


def _d(x):
    return x if isinstance(x, dict) else {}


def _num(x, default=0.0):
    """Safe scalar read of a hand-editable state value: non-numeric / NaN / bool -> default."""
    if isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x):
        return default
    return float(x)


def _int(x, default=0):
    v = _num(x, None)
    return default if v is None else int(v)


def _sanitize_state(st):
    for k in ("open", "kis_rl", "send_retry", "fwd_err_first", "telegram_disabled"):
        if k in st and not isinstance(st[k], dict):
            st.pop(k)
    return st


def _load_state():
    """State for this cycle. The in-memory copy wins while the last write failed (dirty) or the file is unreadable, so that alerts already
    delivered are never re-sent just because the file could not be written."""
    disk = _load(STATE)
    mem = _MEM.get("st") if _MEM.get("path") == str(STATE) else None
    if mem is not None and (_MEM.get("dirty") or disk is None):
        return _sanitize_state(copy.deepcopy(mem))
    return _sanitize_state(disk if disk is not None else {})


def readonly_state():
    """Read-only deep copy of the watch state for stateless callers (Hermes export, CLI, daily summary). They never write state."""
    return _load_state()


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


def _parse_iso(x):
    try:
        t = dt.datetime.fromisoformat(str(x))
        return t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)
    except (ValueError, TypeError):
        return None


def _kis_clear(wst, rl, silent=True):
    if rl.get("active") and silent:
        _d(wst.get("open")).pop("kis_ratelimit", None)          # silent reset (no RECOVERED for a rollover / counter-reset race)
    rl.update(ratio_active=False, ex_active=False, active=False, msg=None, ex_events=[])


def kis_ratelimit_hold(wst):
    """Collector status unusable (stale heartbeat / missing / garbled): keep the previous issue silently (no RECOVERED, no new ISSUE on return)."""
    rl = wst.get("kis_rl") if isinstance(wst, dict) else None
    if not isinstance(rl, dict):
        return None
    rl["hold"] = bool(rl.get("active"))
    return rl.get("msg") if rl.get("active") else None


def kis_ratelimit_issue(k, now, wst=None):
    """Sustained KIS pacing pressure (informational: a pacing issue, not a hard quota). Source: collector status.json keys state, last_cycle.at,
    calls_today, rate_limited_today (EGW00201 per-second responses), errors_today and last_error{at,msg}.
    Evaluated ONLY while the collector is in an active state AND a cycle completed today (KST) at/after the open; otherwise the previous day's
    counters (kept until the first call of a day) could leak in. Two latches kept in wst["kis_rl"]:
      ratio: set when lim*100 > total*25 (total >= 200), cleared when lim*100 < total*10;
      exhausted: 3 'retries exhausted' last_error events (today, each newer than last_error_at_seen) within 30 min; auto-clears after 60 min
                 without a new event (independent of the cumulative day ratio).
    A decrease of calls_today within a day (counter reset race) clears both. Not evaluable: previous state held silently (no RECOVERED)."""
    wst = {} if wst is None else wst
    if not isinstance(wst.get("kis_rl"), dict):
        wst["kis_rl"] = {}
    rl = wst["kis_rl"]
    k = _d(k)
    kst = now.astimezone(kisintra.KST)
    today = kst.date().isoformat()
    try:
        lc = _parse_iso(_d(k.get("last_cycle")).get("at"))
        evaluable = (lc is not None and k.get("state") in KIS_ACTIVE_STATES and kst.weekday() < 5 and kst.time() >= kisintra.OPEN
                     and lc.astimezone(kisintra.KST).date() == kst.date() and lc.astimezone(kisintra.KST).time() >= kisintra.OPEN)
        total, lim = int(k.get("calls_today") or 0), int(k.get("rate_limited_today") or 0)
    except (ValueError, TypeError, AttributeError):
        evaluable = False
    if not evaluable:
        return kis_ratelimit_hold(wst)
    rl["hold"] = False
    first = rl.get("day") is None
    if rl.get("day") != today:                      # new KST day: the collector resets its counters on its first call of the day
        _kis_clear(wst, rl, silent=False)           # an ISSUE delivered yesterday ends with a RECOVERED
        rl.update(day=today, prev_total=_int(rl.get("calls_seen")), calls_seen=0, await_reset=not first, await_cycle=lc.isoformat())
    if rl.get("await_reset"):
        # status.json counters are written at the START of a collector loop, so the first cycle of a day still shows yesterday's counters.
        # Skip evaluation until they visibly dropped below yesterday's final total, or a second cycle completed.
        if total < _int(rl.get("prev_total")) or lc.isoformat() != rl.get("await_cycle"):
            rl["await_reset"] = False
        else:
            return None
    if total < _int(rl.get("calls_seen")):          # counter reset race inside a day
        _kis_clear(wst, rl)
    rl["calls_seen"] = total
    le = _d(k.get("last_error"))
    at = _parse_iso(le.get("at"))
    seen = _parse_iso(rl.get("last_error_at_seen"))
    if at is not None and (seen is None or at > seen):
        if (not first and "retries exhausted" in str(le.get("msg", "")) and at.astimezone(kisintra.KST).date() == kst.date()):
            rl["ex_events"] = (list(rl.get("ex_events") or []) + [at.timestamp()])[-20:]
        rl["last_error_at_seen"] = at.isoformat()
    ev = rl.get("ex_events") or []
    if len(ev) >= KIS_EX_EVENTS and ev[-1] - ev[-KIS_EX_EVENTS] <= KIS_EX_WINDOW_S:
        rl["ex_active"] = True
    if rl.get("ex_active") and ev and now.timestamp() - ev[-1] >= KIS_EX_CLEAR_S:
        rl["ex_active"] = False
    if total >= KIS_RL_MIN_CALLS and lim * 100 < total * KIS_RL_CLEAR_PCT:
        rl["ratio_active"] = False
    elif total >= KIS_RL_MIN_CALLS and lim * 100 > total * KIS_RL_SET_PCT:
        rl["ratio_active"] = True
    rl["active"] = bool(rl.get("ratio_active") or rl.get("ex_active"))
    if not rl["active"]:
        rl["msg"] = None
        return None
    parts = []
    if rl.get("ratio_active"):
        parts.append("%d of %d API calls rate-limited today (KST %s) = %.1f%%, sustained above %d%%" % (lim, total, today, 100.0 * lim / max(total, 1), KIS_RL_SET_PCT))
    if rl.get("ex_active"):
        parts.append("collector reported repeated retries-exhausted errors (%d events, last %s; %d of %d calls rate-limited)" % (
            len(ev), dt.datetime.fromtimestamp(ev[-1], kisintra.KST).strftime("%H:%M KST"), lim, total))
    rl["msg"] = "KIS pacing (informational, not a hard quota): " + "; ".join(parts)
    return rl["msg"]


def forward_error_issue(now, wst):
    """`forward_error` when a forward candidate row stays ERROR > FWD_ERR_AFTER_S. Source: the Hermes export's forward_status.json (written every
    30 min from forward.evaluate_all, so no extra heavy evaluation here). First-seen times live in wst["fwd_err_first"]. If the file is missing,
    stale, withheld, unparseable or has no list `candidates`, the PREVIOUS result is held (timers untouched, no pruning, no false RECOVERED);
    export_failing covers a dead export."""
    held = wst.get("fwd_err_msg") if isinstance(wst.get("fwd_err_msg"), str) else None
    try:
        from . import hermesx
        p = hermesx.EXPORT / "forward_status.json"
        fresh = now.timestamp() - p.stat().st_mtime <= EXPORT_STALE_S
        doc = json.loads(p.read_text())
        rows = doc.get("candidates") if isinstance(doc, dict) else None
    except (OSError, ValueError, ImportError, AttributeError, TypeError):
        return held
    if not fresh or not isinstance(rows, list):
        return held
    errs = {r.get("candidate"): r.get("note") for r in rows if isinstance(r, dict) and r.get("status") == "ERROR"}
    if not isinstance(wst.get("fwd_err_first"), dict):
        wst["fwd_err_first"] = {}
    fe = wst["fwd_err_first"]
    for n in [n for n in fe if n not in errs]:
        fe.pop(n)
    t = now.timestamp()
    for n in errs:
        fe[n] = _num(fe.get(n), t)
    old = sorted(str(n) for n, ts in fe.items() if t - ts > FWD_ERR_AFTER_S)
    msg = None
    if old:
        msg = "forward candidates in ERROR for > %dh: %s; e.g. %s" % (FWD_ERR_AFTER_S // 3600, ",".join(old), scrub(errs.get(old[0]), 80))
    wst["fwd_err_msg"] = msg
    return msg


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
        v = json.loads(p.read_text())
    except (OSError, ValueError):
        return None
    return v if isinstance(v, dict) else None


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
    wst = {} if not isinstance(wst, dict) else wst
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
            iss["kis_state"] = "KIS collector state=%s err=%s" % (k.get("state"), _d(k.get("last_error")).get("msg"))
    if k and _age(k.get("heartbeat"), now) <= 180:
        rl = kis_ratelimit_issue(k, now, wst)
    else:
        rl = kis_ratelimit_hold(wst)            # collector status stale/missing: previous pacing issue is held, not resolved
    if rl:
        iss["kis_ratelimit"] = rl
    fe = forward_error_issue(now, wst)
    if fe:
        iss["forward_error"] = fe
    td = wst.get("telegram_disabled")
    if isinstance(td, dict):
        iss["telegram_disabled"] = "Telegram is not configured (since %s): alerts and summaries are NOT delivered; set the bot token / chat id on the host" % td.get("since")
    ets = _num(wst.get("export_ts"), None)
    if _int(wst.get("export_fail_n")) >= EXPORT_FAIL_N or (ets and now.timestamp() - ets > EXPORT_STALE_S):
        iss["export_failing"] = "hermes export failing: %s consecutive failures, last success %s, last error %s" % (
            _int(wst.get("export_fail_n")), dt.datetime.fromtimestamp(ets, dt.timezone.utc).strftime("%Y-%m-%dT%H:%MZ") if ets else "never",
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
        last = _num(open_.get(k), None)
        interval = REALERT_GDELT_S if (k == "gdelt_degraded" and str(m).startswith("KNOWN DEGRADED")) else REALERT_S
        if k == "kis_ratelimit" and held and last is not None:
            new_open[k] = last
        elif last is None or now_ts - last >= interval:
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
    iss = check_all(now, readonly_state())
    if _d(readonly_state().get("telegram_disabled")):
        L.append("텔레그램: 미설정 (알림/요약이 전달되지 않음)")
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


def _classify(res):
    """notify.send never raises: it returns {'sent': bool, 'reason': str}. -> sent | disabled | client (HTTP 4xx except 429) | failed.
    Test doubles return None (= delivered)."""
    if isinstance(res, dict):
        if res.get("sent") is True:
            return "sent"
        reason = str(res.get("reason", ""))
        if reason.startswith("disabled"):
            return "disabled"
        m = re.search(r"http (\d{3})", reason)
        return "client" if m and 400 <= int(m.group(1)) < 500 and m.group(1) != "429" else "failed"
    return "sent" if (res is None or bool(res)) else "failed"


def _next(e, now):
    """Persisted retry time, clamped so a clock step backwards (NTP) cannot park a key for hours."""
    return min(_num(_d(e).get("next"), 0.0), now + SEND_BACKOFF_MAX_S)


def _may_try(st, key, cyc):
    """Allowed to send now? The send-time budget clock starts at the FIRST send of the cycle (slow checks / summaries do not starve alerts)."""
    if cyc["stop"] or (cyc["t0"] is not None and time.monotonic() - cyc["t0"] > SEND_BUDGET_S):
        return False
    sr, now = _d(st.get("send_retry")), time.time()
    return now >= max(_next(sr.get(key), now), _next(sr.get("*"), now))


def _new_cycle():
    return {"stop": False, "t0": None}


def _try_send(send, text, st, key, cyc, limit=900):
    """-> sent | disabled (Telegram not configured: not a failure) | dropped (HTTP 4xx x CLIENT_DROP_AFTER) | failed | client | skipped.
    Network / 429 / 5xx failure: no more sends this cycle and a GLOBAL backoff ('*') besides the per-key one (1, 2, 4 .. 15 min, persisted).
    Other HTTP 4xx (bad message / chat): only that key backs off, so one poisoned message cannot block the others."""
    if not _may_try(st, key, cyc):
        return "skipped"
    if cyc["t0"] is None:
        cyc["t0"] = time.monotonic()
    try:
        r = _classify(send(scrub(text, limit)))
    except Exception:       # noqa: BLE001
        r = "failed"
    if not isinstance(st.get("send_retry"), dict):
        st["send_retry"] = {}
    sr = st["send_retry"]
    if r in ("failed", "client"):
        if r == "failed":
            cyc["stop"] = True
        for kk in ((key,) if r == "client" else (key, "*")):
            if not isinstance(sr.get(kk), dict):
                sr[kk] = {}
            e = sr[kk]
            e["n"] = _int(e.get("n")) + 1
            e["next"] = time.time() + min(SEND_BACKOFF_S * 2 ** min(e["n"] - 1, 10), SEND_BACKOFF_MAX_S)
        if r == "client" and sr[key]["n"] >= CLIENT_DROP_AFTER:
            sr.pop(key, None)
            _log("message %s dropped after %d HTTP 4xx rejections" % (key, CLIENT_DROP_AFTER))
            return "dropped"
        return r
    sr.pop(key, None)
    sr.pop("*", None)
    if r == "disabled":
        if not isinstance(st.get("telegram_disabled"), dict):
            st["telegram_disabled"] = {"since": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%MZ")}
        if not _TG_LOGGED["v"]:
            _TG_LOGGED["v"] = True
            _log("Telegram is not configured: alerts are dropped (distinct from a delivery failure)")
    else:
        st.pop("telegram_disabled", None)
    return r


def _save_state(st):
    """Atomic write (tmp + os.replace). The in-memory copy is always updated and is the source of truth while the write keeps failing.
    Returns True if the file was written."""
    _MEM.update(path=str(STATE), st=copy.deepcopy(st))
    tmp = STATE.with_name(STATE.name + ".tmp")
    try:
        tmp.write_text(json.dumps(st, indent=1))
        os.replace(tmp, STATE)
        _MEM["dirty"], _MEM["werr"] = False, None
        return True
    except Exception as e:      # noqa: BLE001
        _MEM["dirty"], _MEM["werr"] = True, e
        _log("state write failed: %s" % type(e).__name__)
        try:
            tmp.unlink()
        except OSError:
            pass
        return False


def _deliver(send, out, state, prev_open, cyc):
    """Send keyed alerts. An alert is marked sent only if delivered (or Telegram is disabled); otherwise it stays pending for the backoff retry.
    Returns the number of undelivered alerts."""
    bad = 0
    for key, kind, msg in out:
        r = _try_send(send, msg, state, "alert:" + key, cyc, 600)
        if r in CONSUMED:
            continue
        bad += 1
        if kind == "ISSUE" and key not in prev_open:
            state["open"].pop(key, None)
        else:
            state["open"][key] = prev_open[key]
    return bad


def _fail(st, e, where):
    st["last_error"] = err_record(e, where)
    return False


def _degraded(st, ok, send):
    """watchdog_degraded after DEGRADED_AFTER consecutive failed cycles (6 h re-alert; attempts at most every DEGRADED_TRY_S, counted only when a
    request was actually made). RECOVERED is retried until delivered (degraded_recover_pending). Returns True if st changed."""
    if ok:
        if not (st.get("degraded_alert_ts") or st.get("degraded_recover_pending")):
            return False
        st["degraded_recover_pending"] = True
        if _try_send(send, "[watchdog] RECOVERED watchdog_degraded", st, "degraded_rec", _new_cycle()) in CONSUMED:
            st.pop("degraded_alert_ts", None)
            st.pop("degraded_recover_pending", None)
        return True
    t = time.time()
    if (st.get("degraded_recover_pending") or _int(st.get("fail_streak")) < DEGRADED_AFTER
            or t - _num(st.get("degraded_alert_ts")) < REALERT_S or t - _num(st.get("degraded_try_ts")) < DEGRADED_TRY_S):
        return False
    le = _d(st.get("last_error"))
    r = _try_send(send, "[watchdog] ISSUE watchdog_degraded: %d consecutive failed cycles; last error where=%s type=%s" % (
        _int(st.get("fail_streak")), le.get("where"), le.get("type")), st, "degraded", _new_cycle())
    if r == "skipped":
        return False
    st["degraded_try_ts"] = t
    if r in CONSUMED:
        st["degraded_alert_ts"] = t
    return True


def _proposal_text(st, now):
    """Re-render a pending budget proposal from runs/budget_proposal.json (+ live budget_policy.check) instead of sending stale text.
    -> (text, None) | (None, 'drop') | (None, 'retry'). Dropped when older than 3 days, no longer 'pending', or no longer eligible.
    NOTE: pending_proposal lives in the watch state; if the state file is unwritable AND the process restarts, the in-memory marker is lost
    (the proposal stays 'pending' on disk but propose() will not return its text again)."""
    pp = st.get("pending_proposal")
    if not isinstance(pp, dict):
        pp = st["pending_proposal"] = {"at": now.timestamp(), "text": scrub(pp, 900)}          # legacy format: bare text
    if now.timestamp() - _num(pp.get("at"), now.timestamp()) > PROPOSAL_MAX_AGE_S:
        return None, "drop"
    try:
        from . import budget_policy
        cur = json.loads(budget_policy.PROPOSAL.read_text())
        if cur.get("status") != "pending":
            return None, "drop"
        d = budget_policy.check(now)
        if not d.get("eligible") or d.get("next_cap") != cur.get("to_cap"):
            return None, "drop"
        return scrub(budget_policy.proposal_text(d), 900), None
    except Exception:       # noqa: BLE001
        return (pp["text"], None) if isinstance(pp.get("text"), str) and pp["text"] else (None, "retry")


def run_forever(stop=lambda: False, sleep=time.sleep, send=None):
    send = send or (lambda t: notify.send(t))
    while not stop():
        now = dt.datetime.now(dt.timezone.utc)
        st = _load_state()
        cyc = _new_cycle()
        ok, stage, bp_ok = True, "load", False
        prev_streak = _int(st.get("fail_streak"))
        try:
            stage = "check_all"
            issues = {k: v for k, v in check_all(now, st).items() if k not in NO_TELEGRAM}
            stage = "diff_alerts"
            prev_open = dict(_d(st.get("open")))
            out, st = diff_alerts_keyed(issues, st, time.time())
            sr = _d(st.get("send_retry"))
            for kk in [x for x in sr if x.startswith("alert:") and x[6:] not in issues and x[6:] not in prev_open]:
                sr.pop(kk)                           # the issue cleared before it was ever delivered: forget its backoff
            stage = "send_alerts"
            if _deliver(send, out, st, prev_open, cyc):      # undelivered alerts stay pending; the rest of the cycle still runs
                ok = _fail(st, RuntimeError("alert delivery failed; pending alerts retried with backoff"), "send_alerts")
            day = now.strftime("%Y-%m-%d")
            if now.hour >= SUMMARY_HOUR_UTC and st.get("summary_day") != day:
                st["summary_pending"] = day          # catch-up: stays due after the 23:xx window until delivered (or the next day's window)
            due = st.get("summary_pending")
            fresh = None
            if isinstance(due, str) and due != st.get("summary_day"):
                stage = "daily_summary"
                r = "skipped"
                if _may_try(st, "summary", cyc):     # the (expensive) summary is only computed when it can be sent
                    r = _try_send(send, daily_summary(now), st, "summary", cyc, 4000)
                if r in CONSUMED:
                    st["summary_day"] = due          # only a delivered summary consumes the day; otherwise retried with backoff
                    st.pop("summary_pending", None)
                    stage = "budget_policy"
                    try:      # budget-increase PROPOSAL only (deterministic); the cap itself is changed solely by the owner on the host
                        from . import budget_policy
                        txt, _d_ = budget_policy.propose(now)
                        if txt:
                            fresh = scrub(txt, 900)
                            st["pending_proposal"] = {"at": now.timestamp()}   # propose() records 'pending' on disk and never returns the text again
                        bp_ok = True
                    except Exception as e:      # noqa: BLE001
                        ok = _fail(st, e, "budget_policy")
                else:
                    ok = _fail(st, RuntimeError("daily summary undelivered; retry with backoff"), "daily_summary")
            elif due:
                st.pop("summary_pending", None)
            if st.get("pending_proposal"):
                stage = "proposal"
                text, action = (fresh, None) if fresh else _proposal_text(st, now)
                if action == "drop":
                    st.pop("pending_proposal", None)
                elif text:
                    if _try_send(send, text, st, "proposal", cyc) in CONSUMED:
                        st.pop("pending_proposal", None)
                    else:
                        ok = _fail(st, RuntimeError("budget proposal undelivered; retry with backoff"), "proposal")
            stage = "export"
            t = time.time()
            if t - _num(st.get("export_ts")) >= EXPORT_EVERY_S and t >= _num(st.get("export_next_retry")):
                try:
                    from . import hermesx
                    rep = hermesx.write_all(now)
                    st["export_ts"], st["export_withheld"] = time.time(), rep["withheld"]
                    st.pop("export_next_retry", None)
                    st["export_fail_n"], st["export_error"] = 0, None
                except Exception as e:      # noqa: BLE001  export_ts is NOT advanced: retry with backoff instead of waiting EXPORT_EVERY_S
                    n = _int(st.get("export_fail_n")) + 1
                    st["export_fail_n"] = n
                    st["export_next_retry"] = time.time() + export_backoff(n)
                    st["export_error"] = err_record(e, "export")
            st["heartbeat"] = now.isoformat()
        except Exception as e:      # noqa: BLE001
            ok = _fail(st, e, stage)
        if ok:
            st["fail_streak"] = 0
            resolve_last_error(st, now, keep_budget_policy=not bp_ok)
        else:
            st["fail_streak"] = _int(st.get("fail_streak")) + 1
        if not _save_state(st):                      # the file is unwritable: count it as a failed cycle, keep going from memory
            st["fail_streak"] = prev_streak + 1
            ok = _fail(st, _MEM.get("werr") or OSError("state write failed"), "state_write")
            _MEM["st"] = copy.deepcopy(st)
        if _degraded(st, ok, send):
            _save_state(st)
        sleep(60)
