"""Watchdog + daily Telegram summary. NO LLM. Runs in container `tp-watch` (Telegram vars only, data read-only, runs rw).

Checks every 60 s (heartbeat ages, per-collector freshness, KIS during the KR session, disk, budget) and alerts once per issue
(re-alert after 6 h; a recovery message when it clears). Daily summary at 23:00 UTC (08:00 KST). Every outgoing text passes the
notify secret scrubber. The watchdog never deletes anything and never restarts anything (restart policy handles crashes)."""
import datetime as dt
import json
import shutil
import sqlite3
import time

from . import budget, config, deriv, hl, kisintra, news, notify
from .config import DATA, RUNS, scrub

STATE = RUNS / "watch_state.json"
SUMMARY_HOUR_UTC = 23
REALERT_S = 6 * 3600


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


def check_all(now=None):
    """Return {issue_key: message}. Pure function of the status files / DBs (testable)."""
    now = now or dt.datetime.now(dt.timezone.utc)
    iss = {}
    s = _load(news.STATUS)
    if not s or _age(s.get("updated"), now) > 180:
        iss["news_heartbeat"] = "news collector heartbeat stale/missing"
    else:
        for k, j in s.get("jobs", {}).items():
            lim = {"gdelt": 10800, "fng": 30000, "us_daily": 30000, "parquet": 7200, "retention": 100000}.get(k.split(":")[0], 2400)
            if j.get("fails", 0) >= 3 or (j.get("last_ok") and _age(j["last_ok"], now) > lim and not k.startswith("gdelt")):
                iss["news_job_" + k] = "news job %s fails=%s last_ok=%s err=%s" % (k, j.get("fails"), j.get("last_ok"), j.get("last_err"))
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


def diff_alerts(issues, state, now_ts):
    """Return (messages_to_send, new_state). Alert on new issues, re-alert after REALERT_S, announce recoveries."""
    open_ = state.get("open", {})
    msgs, new_open = [], {}
    for k, m in issues.items():
        last = open_.get(k)
        if last is None or now_ts - last >= REALERT_S:
            msgs.append("[watchdog] ISSUE %s: %s" % (k, m))
            new_open[k] = now_ts
        else:
            new_open[k] = last
    for k in open_:
        if k not in issues:
            msgs.append("[watchdog] RECOVERED %s" % k)
    return msgs, dict(state, open=new_open)


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
    L = ["[daily] %s UTC" % now.strftime("%Y-%m-%d %H:%M")]
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
                                                                                o["risk_multiplier"], r[3], r[2], r[0][5:16]))
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


def run_forever(stop=lambda: False, sleep=time.sleep, send=None):
    send = send or (lambda t: notify.send(t))
    while not stop():
        now = dt.datetime.now(dt.timezone.utc)
        st = _load(STATE) or {}
        try:
            msgs, st = diff_alerts(check_all(now), st, time.time())
            for m in msgs:
                send(scrub(m, 600))
            day = now.strftime("%Y-%m-%d")
            if now.hour >= SUMMARY_HOUR_UTC and st.get("summary_day") != day:
                send(daily_summary(now))
                st["summary_day"] = day
            st["heartbeat"] = now.isoformat()
        except Exception as e:      # noqa: BLE001
            st["last_error"] = scrub(e, 200)
        STATE.write_text(json.dumps(st, indent=1))
        sleep(60)
