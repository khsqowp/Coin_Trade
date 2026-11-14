"""KIS PAPER (mock investing) intraday 1-minute bar collector for KRX stocks. READ-ONLY quotation calls only.

No order code exists here; kis.ALLOWED rejects every path that is not a quotation/ranking GET or the token call.
Limits respected: token issuance 1/min (one token per ~20 h, retry no faster than 65 s), >= 0.7 s between calls
(paper API ~2 req/s), hard daily call cap, nothing is collected outside KST 09:00-15:30 (+ a final 15:35 sweep).

Output: data/intraday/kr/<YYYYMMDD>/<code>.parquet (UTC index, open/high/low/close/volume),
        data/intraday/kr/snapshots_<YYYYMMDD>.jsonl (price, change %, cumulative volume per poll),
        data/intraday/kr/status.json (heartbeat, per-symbol last bar, call counters, errors).
"""
import datetime as dt
import json
import os
import time

import pandas as pd

from . import kis
from .config import DATA, scrub

KR_DIR = DATA / "intraday" / "kr"
STATUS = KR_DIR / "status.json"
KST = dt.timezone(dt.timedelta(hours=9))
MIN_GAP = 0.7
MAX_CALLS_PER_DAY = int(os.environ.get("TP_KIS_MAX_CALLS_DAY", "8000"))
CYCLE_SEC = int(os.environ.get("TP_KIS_CYCLE_SEC", "300"))
OPEN, CLOSE, LAST_SWEEP = dt.time(9, 0), dt.time(15, 30), dt.time(15, 35)

TIME_PATH = "/uapi/domestic-stock/v1/quotations/inquire-time-itemchartprice"
RANK_PATH = "/uapi/domestic-stock/v1/ranking/fluctuation"

# KOSPI large caps (static core). Names are informational.
CORE = {"005930": "Samsung Electronics", "000660": "SK hynix", "373220": "LG Energy Solution",
        "207940": "Samsung Biologics", "005380": "Hyundai Motor", "000270": "Kia", "068270": "Celltrion",
        "105560": "KB Financial", "035420": "NAVER", "055550": "Shinhan Financial", "005490": "POSCO Holdings",
        "012330": "Hyundai Mobis", "028260": "Samsung C&T", "035720": "Kakao", "051910": "LG Chem",
        "006400": "Samsung SDI", "086790": "Hana Financial", "066570": "LG Electronics", "034730": "SK",
        "017670": "SK Telecom", "015760": "KEPCO", "033780": "KT&G", "010130": "Korea Zinc",
        "329180": "HD Hyundai Heavy", "012450": "Hanwha Aerospace", "316140": "Woori Financial"}
MAX_UNIVERSE = 30

_last = {"t": 0.0}
CALLS = {"day": None, "n": 0, "errors": 0, "rate_limited": 0}


class Stop(Exception):
    pass


def kst_now():
    return dt.datetime.now(dt.timezone.utc).astimezone(KST)


def in_session(t):
    return t.weekday() < 5 and OPEN <= t.time() <= LAST_SWEEP


def count_call(now):
    d = now.date().isoformat()
    if CALLS["day"] != d:
        CALLS.update(day=d, n=0, errors=0, rate_limited=0)
    if CALLS["n"] >= MAX_CALLS_PER_DAY:
        raise Stop("daily call cap reached (%d)" % MAX_CALLS_PER_DAY)
    CALLS["n"] += 1


def api_get(path, tr_id, params, sleep=time.sleep, tries=4):
    key, sec = kis._creds()
    for i in range(tries):
        wait = _last["t"] + MIN_GAP - time.monotonic()
        if wait > 0:
            sleep(wait)
        count_call(kst_now())
        hdr = {"authorization": "Bearer " + kis.get_token(), "appkey": key, "appsecret": sec,
               "tr_id": tr_id, "custtype": "P"}
        r = kis._req("GET", path, headers=hdr, params=params)
        _last["t"] = time.monotonic()
        txt = r.text
        if "EGW00201" in txt:                       # per-second limit
            CALLS["rate_limited"] += 1
            sleep(1.5 * (i + 1))
            continue
        if "EGW00123" in txt or "EGW00121" in txt:  # token expired / invalid
            kis.invalidate_token()
            sleep(65)
            continue
        try:
            return r.status_code, r.json()
        except ValueError:
            CALLS["errors"] += 1
            return r.status_code, {"rt_cd": "-1", "msg1": scrub(txt, 120)}
    CALLS["errors"] += 1
    return 429, {"rt_cd": "-1", "msg1": "retries exhausted"}


def parse_minutes(j, day):
    """KIS output2 rows -> DataFrame (UTC index). Only rows dated `day` (YYYYMMDD) are kept."""
    rows = []
    for p in j.get("output2") or []:
        if p.get("stck_bsop_date") != day or not p.get("stck_cntg_hour"):
            continue
        ts = dt.datetime.strptime(day + p["stck_cntg_hour"], "%Y%m%d%H%M%S").replace(tzinfo=KST)
        rows.append((ts.astimezone(dt.timezone.utc), p["stck_oprc"], p["stck_hgpr"], p["stck_lwpr"], p["stck_prpr"], p["cntg_vol"]))
    if not rows:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
    df = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close", "volume"]).set_index("ts")
    return df.astype(float).sort_index()


def fetch_minutes_page(code, upto_hhmmss, day):
    st, j = api_get(TIME_PATH, "FHKST03010200", {
        "FID_ETC_CLS_CODE": "", "FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": code,
        "FID_INPUT_HOUR_1": upto_hhmmss, "FID_PW_DATA_INCU_YN": "N"})
    if st != 200 or j.get("rt_cd") != "0":
        raise RuntimeError("HTTP %s rt_cd=%s msg_cd=%s %s" % (st, j.get("rt_cd"), j.get("msg_cd"), scrub(j.get("msg1", ""), 100)))
    return parse_minutes(j, day), j.get("output1") or {}


def day_path(day, code):
    return KR_DIR / day / (code + ".parquet")


def load_day(day, code):
    p = day_path(day, code)
    return pd.read_parquet(p) if p.exists() else pd.DataFrame(columns=["open", "high", "low", "close", "volume"])


def merge_save(day, code, new):
    old = load_day(day, code)
    df = pd.concat([old, new]) if len(old) else new
    df = df[~df.index.duplicated(keep="last")].sort_index()
    p = day_path(day, code)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    df.to_parquet(tmp)
    tmp.replace(p)
    return df


def collect_symbol(code, now, sleep=time.sleep, max_pages=16):
    """Fetch the newest minute bars; page backwards until the stored history is joined (or 09:00). Returns (n_new_rows, snapshot)."""
    day = now.strftime("%Y%m%d")
    have = load_day(day, code)
    need_from = have.index.max() if len(have) else None
    upto = min(now.time(), CLOSE)
    hhmmss = upto.strftime("%H%M%S")
    got, snap = [], None
    for _ in range(max_pages):
        df, o1 = fetch_minutes_page(code, hhmmss, day)
        snap = snap or o1
        if df.empty:
            break
        got.append(df)
        earliest = df.index.min()
        e_kst = earliest.astimezone(KST)
        if e_kst.time() <= dt.time(9, 1) or (need_from is not None and earliest <= need_from):
            break
        hhmmss = (e_kst - dt.timedelta(minutes=1)).strftime("%H%M%S")
    if not got:
        return 0, snap
    new = pd.concat(got)
    before = len(have)
    merged = merge_save(day, code, new)
    return len(merged) - before, snap


def write_snapshot(code, snap, now):
    if not snap:
        return
    try:
        price = float(snap.get("stck_prpr"))
        chg = float(snap.get("prdy_ctrt"))
    except (TypeError, ValueError):
        return
    rec = {"t": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "code": code, "price": price,
           "chg_pct": chg, "acml_vol": snap.get("acml_vol"), "prdy_close": round(price / (1 + chg / 100), 2) if chg > -100 else None}
    KR_DIR.mkdir(parents=True, exist_ok=True)
    with open(KR_DIR / ("snapshots_%s.jsonl" % now.strftime("%Y%m%d")), "a") as f:
        f.write(json.dumps(rec) + "\n")


def probe_ranking(day_state):
    """Try the fluctuation-rank API once per day. Paper (VTS) servers usually do not support it."""
    try:
        st, j = api_get(RANK_PATH, "FHPST01700000", {
            "fid_rsfl_rate2": "", "fid_cond_mrkt_div_code": "J", "fid_cond_scr_div_code": "20170", "fid_input_iscd": "0000",
            "fid_rank_sort_cls_code": "0", "fid_input_cnt_1": "0", "fid_prc_cls_code": "0", "fid_input_price_1": "",
            "fid_input_price_2": "", "fid_vol_cnt": "", "fid_trgt_cls_code": "0", "fid_trgt_exls_cls_code": "0",
            "fid_div_cls_code": "0", "fid_rsfl_rate1": ""})
    except Exception as e:      # noqa: BLE001
        day_state["ranking"] = {"supported": False, "reason": scrub(e, 150)}
        return []
    if st == 200 and j.get("rt_cd") == "0" and j.get("output"):
        codes = [r["stck_shrn_iscd"] for r in j["output"] if r.get("stck_shrn_iscd")]
        day_state["ranking"] = {"supported": True, "n": len(codes)}
        return codes
    day_state["ranking"] = {"supported": False, "reason": "HTTP %s rt_cd=%s msg=%s" % (st, j.get("rt_cd"), scrub(j.get("msg1", ""), 120))}
    return []


def build_universe(extra):
    u = list(CORE)
    for c in extra:
        if c not in u and len(u) < MAX_UNIVERSE:
            u.append(c)
    return u


def write_status(obj):
    KR_DIR.mkdir(parents=True, exist_ok=True)
    tmp = STATUS.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, indent=1, default=str))
    tmp.replace(STATUS)


def run_forever(stop=lambda: False, sleep=time.sleep):
    st = {"started": dt.datetime.now(dt.timezone.utc).isoformat(), "state": "init", "symbols": {}, "last_error": None,
          "ranking": {"supported": None}, "paper_endpoint": kis.BASE}
    next_cycle, day_key, universe, prewarmed = 0.0, None, list(CORE), None
    while not stop():
        now = kst_now()
        st.update(heartbeat=now.isoformat(), calls_today=CALLS["n"], rate_limited_today=CALLS["rate_limited"], errors_today=CALLS["errors"])
        try:
            if now.weekday() < 5 and dt.time(8, 55) <= now.time() < OPEN and prewarmed != now.date():
                kis.get_token()
                prewarmed = now.date()
            if not in_session(now):
                st["state"] = "waiting_market_open"
                write_status(st)
                sleep(30)
                continue
            if day_key != now.date():
                day_key = now.date()
                st["symbols"] = {}
                st["ranking"] = {"supported": None}
                universe = build_universe(probe_ranking(st))
                st["universe"] = universe
            if time.monotonic() < next_cycle:
                st["state"] = "sleeping_between_cycles"
                write_status(st)
                sleep(5)
                continue
            st["state"] = "collecting"
            total_new = 0
            for code in universe:
                if stop():
                    break
                try:
                    n, snap = collect_symbol(code, now, sleep=sleep)
                    write_snapshot(code, snap, now)
                    s = st["symbols"].setdefault(code, {"bars_today": 0})
                    s["bars_today"] = len(load_day(now.strftime("%Y%m%d"), code))
                    s["last_ok"] = dt.datetime.now(dt.timezone.utc).isoformat()
                    s.pop("error", None)
                    total_new += n
                    if n == 0 and code == universe[0] and s["bars_today"] == 0:
                        st["state"] = "no_data_today(holiday?)"
                        break
                except Stop:
                    raise
                except Exception as e:      # noqa: BLE001
                    CALLS["errors"] += 1
                    st["symbols"].setdefault(code, {"bars_today": 0})["error"] = scrub(e, 150)
                    st["last_error"] = {"at": now.isoformat(), "code": code, "msg": scrub(e, 150)}
            st["last_cycle"] = {"at": now.isoformat(), "new_rows": total_new}
            next_cycle = time.monotonic() + CYCLE_SEC
            write_status(st)
        except Stop as e:
            st["state"] = "stopped_daily_cap"
            st["last_error"] = {"at": now.isoformat(), "msg": str(e)}
            write_status(st)
            sleep(600)
        except Exception as e:              # noqa: BLE001 token failures etc.
            st["state"] = "error_backoff"
            st["last_error"] = {"at": now.isoformat(), "msg": scrub(e, 200)}
            write_status(st)
            sleep(70)                       # also respects the 1/min token issuance limit


def status_report():
    """Combined health report for all collectors (read-only; used by `collector-status`)."""
    from . import news
    now = dt.datetime.now(dt.timezone.utc)
    rep = {"now": now.isoformat(), "news": {}, "kis_intraday": {}, "us_daily": {}}
    if news.STATUS.exists():
        s = json.loads(news.STATUS.read_text())
        age = (now - dt.datetime.fromisoformat(s["updated"].replace("Z", "+00:00"))).total_seconds()
        rep["news"] = {"heartbeat_age_s": round(age), "alive": age < 300,
                       "jobs": {k: {"fails": v["fails"], "last_ok": v["last_ok"], "last_err": v["last_err"]} for k, v in s["jobs"].items()},
                       "counts": news.counts()}
    if STATUS.exists():
        s = json.loads(STATUS.read_text())
        hb = dt.datetime.fromisoformat(s["heartbeat"]).astimezone(dt.timezone.utc)
        s["heartbeat_age_s"] = round((now - hb).total_seconds())
        s["alive"] = s["heartbeat_age_s"] < 300
        files = sorted(KR_DIR.glob("2*/*.parquet"))
        days = sorted({f.parent.name for f in files})
        s["stored_days"] = days
        s["stored_files"] = len(files)
        if days:
            last = days[-1]
            s["last_day_rows"] = sum(len(pd.read_parquet(f)) for f in (KR_DIR / last).glob("*.parquet"))
        rep["kis_intraday"] = s
    try:
        from . import deriv
        rep["deriv"] = {"counts": deriv.counts(), "status": json.loads(deriv.STATUS.read_text()) if deriv.STATUS.exists() else None}
    except Exception as e:      # noqa: BLE001
        rep["deriv"] = {"error": scrub(e, 100)}
    try:
        from . import store
        rep["us_daily"] = [{k: m[k] for k in ("symbol", "rows", "first_ts", "last_ts", "fetched_at")}
                           for m in store.list_datasets() if m["source"] == "yahoo"]
    except Exception as e:      # noqa: BLE001
        rep["us_daily"] = {"error": scrub(e, 100)}
    return rep
