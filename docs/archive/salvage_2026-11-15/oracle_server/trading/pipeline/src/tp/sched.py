"""Regime-agent scheduler (the ONLY LLM scheduler). ON by default in its own container `tp-sched`; stop with `./svc.sh stop sched`
or `touch runs/SCHED_DISABLED` (checked every loop; remove the file to resume).

Cadence: crypto hourly (:02), kr twice a day (23:30 and 06:40 UTC = 08:30 / 15:40 KST), us twice a day (12:30 and 21:30 UTC).
Daily cap: scheduler spend (ledger rows with run_id 'sched-*') per UTC day <= TP_DAILY_CAP (default $0.30); beyond that the day's
remaining runs are skipped (no row is logged for skipped runs, the status file counts them). The global task budget (80% stop) also applies.
Carry gate (crypto only): the LLM is called only if >= 6h since the last LLM judgement, or the deterministic price regime changed,
or |BTC 4h move| > 2.5%, or >= 3 new crypto news items and >= 2h elapsed. Otherwise the previous judgement is carried into a NEW log row
(status 'carried', cost 0) so the forward record stays gap-free.
Safety: the scheduler only calls regime.run (no tools, schema-validated, risk can only be reduced). Nothing here can place orders,
change configuration, or send data anywhere except the LLM providers and the append-only log."""
import datetime as dt
import json
import time

from . import budget, config, regime, regime_det
from .config import RUNS, scrub

STATUS = RUNS / "sched_status.json"          # runs/ is the only writable mount of the scheduler container
DISABLE_FLAG = RUNS / "SCHED_DISABLED"
TIMES = {"kr": ("23:30", "06:40"), "us": ("12:30", "21:30")}
CRYPTO_MINUTE = 2
MAX_AGE_LLM_H = 6.0


def now_utc():
    return dt.datetime.now(dt.timezone.utc)


def due_slots(now, last_slots):
    """Return [(market, slot_key)] due now. Slot keys are unique per day/hour so each slot runs once (catch-up window 3h)."""
    out = []
    if now.minute >= CRYPTO_MINUTE:
        k = now.strftime("%Y%m%dT%H")
        if last_slots.get("crypto") != k:
            out.append(("crypto", k))
    for m, ts in TIMES.items():
        for t in ts:
            hh, mm = map(int, t.split(":"))
            slot = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
            if slot > now:
                slot -= dt.timedelta(days=1)
            if now - slot <= dt.timedelta(hours=3):
                k = slot.strftime("%Y%m%dT%H%M")
                if last_slots.get(m) != k and (m, k) not in out:
                    out.append((m, k))
    return out


def last_llm_row(market, con):
    return con.execute("SELECT id, asof, logged_at, output_json, input_json FROM regime_log WHERE market=? AND source='llm' ORDER BY id DESC LIMIT 1",
                       (market,)).fetchone()


def det_label(asof):
    from . import store
    try:
        df = store.get_ohlcv("BTC/USDT", "4h")
        df = df[df.index + dt.timedelta(hours=4) <= asof]
        return regime_det.classify_last(df), float(df["close"].iloc[-1] / df["close"].iloc[-2] - 1)
    except Exception:       # noqa: BLE001
        return "unknown", 0.0


def crypto_needs_llm(now, con, news_con, prev_det):
    row = last_llm_row("crypto", con)
    if row is None:
        return True, "first run"
    last_t = dt.datetime.strptime(row[2], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)
    age_h = (now - last_t).total_seconds() / 3600
    if age_h >= MAX_AGE_LLM_H:
        return True, "age %.1fh" % age_h
    lab, move = det_label(now)
    if prev_det and lab != prev_det:
        return True, "regime %s->%s" % (prev_det, lab)
    if abs(move) > 0.025:
        return True, "4h move %.1f%%" % (move * 100)
    if age_h >= 2 and news_con is not None:
        n = news_con.execute("SELECT COUNT(*) FROM items WHERE fetched_at>? AND source IN ('coindesk','gdelt:crypto_policy')",
                             (row[2],)).fetchone()[0]
        if n >= 3:
            return True, "%d new crypto news" % n
    return False, "carry (age %.1fh, det=%s)" % (age_h, lab)


def carry(market, now, con, reason):
    row = last_llm_row(market, con)
    if row is None:
        return None
    out = json.loads(row[3])
    return regime.append_log(con, now.strftime("%Y-%m-%dT%H:%M:%SZ"), market, {"carried_from_row": row[0], "reason": reason}, out,
                             {"carried": True}, "carried", "carry", "-", "-", 0.0)


def run_slot(market, now, state, news_con):
    from . import liqmap
    con = regime.log_con()
    try:
        if market == "crypto":
            go, why = crypto_needs_llm(now, con, news_con, state.get("det_label"))
            state["det_label"], _ = det_label(now)
            if not go:
                carry(market, now, con, why)
                return {"market": market, "mode": "carried", "why": why}
        extra = None
        if market == "crypto":
            extra = {}
            for coin in ("BTC", "ETH"):
                extra.update(liqmap.regime_features(coin=coin))
        r = regime.run(market, asof=now, news_con=news_con, extra_features=extra,
                       run_id="sched-%s-%s" % (market, now.strftime("%Y%m%dT%H%M")))
        return {"market": market, "mode": "llm", "status": r["status"], "cost": r["cost_usd"], "regime": r["output"]["regime"],
                "risk_multiplier": r["output"]["risk_multiplier"]}
    finally:
        con.close()


def write_status(st):
    STATUS.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATUS.with_suffix(".tmp")
    tmp.write_text(json.dumps(st, indent=1, default=str))
    tmp.replace(STATUS)


def run_forever(stop=lambda: False, sleep=time.sleep):
    from . import news
    st = {"started": now_utc().isoformat(), "daily_cap_usd": config.DAILY_CAP, "last_slots": {}, "runs": 0, "skipped_daily_cap": 0,
          "carried": 0, "errors": 0, "last": None, "enabled": True}
    if STATUS.exists():                                   # restart recovery: do not repeat slots that already ran
        try:
            old = json.loads(STATUS.read_text())
            st["last_slots"] = old.get("last_slots", {})
            for k in ("runs", "skipped_daily_cap", "carried", "errors"):
                st[k] = old.get(k, 0)
            st["det_label"] = old.get("det_label")
        except ValueError:
            pass
    while not stop():
        now = now_utc()
        st["heartbeat"] = now.isoformat()
        st["sched_spent_today_usd"] = round(budget.sched_spent_today(), 6)
        st["enabled"] = not DISABLE_FLAG.exists()
        if st["enabled"]:
            for market, key in due_slots(now, st["last_slots"]):
                try:
                    if budget.DAILY_CAP > 0 and budget.sched_spent_today() >= budget.DAILY_CAP:
                        st["skipped_daily_cap"] += 1
                        st["last_slots"][market] = key
                        st["last"] = {"market": market, "mode": "skipped_daily_cap"}
                        continue
                    ncon = news.ro_con() if news.DB.exists() else None
                    res = run_slot(market, now, st, ncon)
                    st["runs"] += 1
                    st["carried"] += res["mode"] == "carried"
                    st["last"] = dict(res, at=now.isoformat())
                    st["last_slots"][market] = key
                except Exception as e:      # noqa: BLE001  never crash the daemon
                    st["errors"] += 1
                    st["last"] = {"market": market, "mode": "error", "msg": scrub(e, 200), "at": now.isoformat()}
                    st["last_slots"][market] = key        # do not hot-loop a failing slot
        write_status(st)
        sleep(30)
