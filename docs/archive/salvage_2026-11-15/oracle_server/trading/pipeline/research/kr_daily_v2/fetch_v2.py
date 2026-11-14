"""KR-daily-v2 full-universe daily history fetch (READ-ONLY quotation calls via tp.kis._get_chart: same path/params/pacing as kis.fetch_daily).

Why not kis.fetch_daily directly: it walks back from TODAY and stops at the first empty 140-day window, which returns nothing for delisted codes
and truncates listed names after long trading halts. This wrapper uses the identical request (FHKST03010100, FID_ORG_ADJ_PRC=0 adjusted prices),
the module's own rate-limited _get_chart (0.8 s spacing + EGW00201 back-off), but starts at each name's delisting date and tolerates halt gaps.
Additionally keeps acml_tr_pbmn (traded value, KRW) for liquidity filters.

Order: a fixed random permutation (seed 20261104) of listed + delisted non-SPAC codes, so an incomplete fetch is an unbiased random subset.
Pauses on weekdays 08:50-15:40 KST so the intraday KIS collector (same app key, ~2 req/s budget) is not disturbed.
"""
import csv, datetime as dt, json, random, sys, time
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
from tp import kis

KR = Path("/app/kr"); OUT = KR / "data"; OUT.mkdir(exist_ok=True)
LOG = KR / "fetch_log.jsonl"
KST = ZoneInfo("Asia/Seoul")
END = dt.date(2026, 11, 3)          # fixed common end date (last complete session at design time)
FLOOR = dt.date(2011, 5, 1)          # 12m+ lookback before the 2012-06-01 evaluation start
WIN = 140


def pause_for_market():
    while True:
        now = dt.datetime.now(KST)
        if now.weekday() < 5 and dt.time(8, 50) <= now.time() < dt.time(15, 40):
            time.sleep(60)
            continue
        return


def hdr():
    key, sec = kis._creds()
    return {"authorization": "Bearer " + kis.get_token(), "appkey": key, "appsecret": sec, "tr_id": "FHKST03010100", "custtype": "P"}


def call(code, a, b):
    for attempt in range(3):
        r = kis._get_chart(hdr(), {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": code, "FID_INPUT_DATE_1": a.strftime("%Y%m%d"),
                                   "FID_INPUT_DATE_2": b.strftime("%Y%m%d"), "FID_PERIOD_DIV_CODE": "D", "FID_ORG_ADJ_PRC": "0"})
        j = r.json() if r.status_code == 200 else {}
        if r.status_code == 200 and j.get("rt_cd") == "0":
            return [p for p in (j.get("output2") or []) if p.get("stck_bsop_date")]
        msg = str(j.get("msg_cd", "")) + " " + str(j.get("msg1", r.text))[:80]
        if "EGW00123" in msg or "token" in msg.lower():
            kis.invalidate_token(); time.sleep(65)
        else:
            time.sleep(3 * (attempt + 1))
    raise RuntimeError("chart failed %s %s..%s: %s" % (code, a, b, kis.scrub(msg, 120)))


def fetch(code, end, lower):
    rows, empty, got = [], 0, False
    while end >= lower:
        pause_for_market()
        start = max(end - dt.timedelta(days=WIN), lower)
        part = call(code, start, end)
        if part:
            rows.extend(part); got = True; empty = 0
            end = dt.datetime.strptime(min(p["stck_bsop_date"] for p in part), "%Y%m%d").date() - dt.timedelta(days=1)
        else:
            empty += 1
            if (got and empty >= 4) or (not got and empty >= 8):
                break
            end = start - dt.timedelta(days=1)
    if not rows:
        return None
    df = pd.DataFrame(rows)
    df.index = pd.to_datetime(df["stck_bsop_date"])
    df = df.rename(columns={"stck_oprc": "open", "stck_hgpr": "high", "stck_lwpr": "low", "stck_clpr": "close", "acml_vol": "volume",
                            "acml_tr_pbmn": "value"})[["open", "high", "low", "close", "volume", "value"]].astype(float).sort_index()
    return df[~df.index.duplicated()]


TRANSFER_WORDS = ("이전상장", "유가증권시장 상장", "코스닥시장 상장")


def segments(U):
    """One fetch segment per instrument (addendum A2). Market transfers (KONEX->KOSDAQ->KOSPI, same code/company) are ONE continuous
    series over the full window; a code whose terminal delisting precedes a much later re-listing becomes two instruments (<code>_old, <code>)."""
    by = {}
    for u in U:
        by.setdefault(u["code"], []).append(u)
    segs = []
    for code, v in by.items():
        L = [x for x in v if x["status"] == "listed"]
        D = [x for x in v if x["status"] == "delisted"]
        ldate = L[0]["listed"] if L else ""
        transfer = [d for d in D if any(w in d["reason"] for w in TRANSFER_WORDS) or (ldate and d["delisted"] == ldate)]
        term = [d for d in D if d not in transfer]
        if L and term and max(t["delisted"] for t in term) < ldate:          # delisted, later re-listed under the same code
            old = max(t["delisted"] for t in term)
            if old >= "2011-06-01":
                segs.append({"key": code + "_old", "code": code, "end": old, "lower": "", "status": "delisted"})
            segs.append({"key": code, "code": code, "end": "", "lower": ldate, "status": "listed"})
        elif L:
            segs.append({"key": code, "code": code, "end": "", "lower": "" if transfer else ldate, "status": "listed"})
        else:
            end = max(t["delisted"] for t in term) if term else max(d["delisted"] for d in D)
            if end >= "2011-06-01":
                segs.append({"key": code, "code": code, "end": end, "lower": "", "status": "delisted"})
    return segs


def main():
    U = list(csv.DictReader(open(KR / "universe" / "universe_raw.csv", encoding="utf-8")))
    U = [u for u in U if "스팩" not in u["name"] and "기업인수목적" not in u["name"]]
    U = segments(U)
    U.sort(key=lambda s: s["key"])
    random.Random(20261104).shuffle(U)
    for i, u in enumerate(U):
        code = u["code"]; p = OUT / (u["key"] + ".parquet")
        if p.exists() or (OUT / (u["key"] + ".none")).exists():
            continue
        end = min(END, dt.date.fromisoformat(u["end"])) if u["end"] else END
        lower = FLOOR
        if u["lower"]:
            lower = max(FLOOR, dt.date.fromisoformat(u["lower"]) - dt.timedelta(days=7))
        t0 = time.time()
        try:
            df = fetch(code, end, lower)
            if df is None:
                (OUT / (u["key"] + ".none")).write_text("no rows"); rec = {"code": u["key"], "rows": 0}
            else:
                df.to_parquet(p); rec = {"code": u["key"], "rows": len(df), "first": str(df.index[0].date()), "last": str(df.index[-1].date())}
        except Exception as e:
            rec = {"code": u["key"], "error": kis.scrub(e, 200)}
        rec.update({"i": i, "n": len(U), "status": u["status"], "sec": round(time.time() - t0, 1), "at": dt.datetime.now(KST).isoformat(timespec="seconds")})
        with open(LOG, "a") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
