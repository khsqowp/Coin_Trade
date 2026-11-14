"""KIS (Korea Investment & Securities) PAPER-trading quotation client. Read-only, daily candles.

Hard guards: host is fixed to the paper (VTS) endpoint; only the token and daily-chart paths are
allowed -- there is no order code in this module and order paths are rejected by the allow-list.
"""
import datetime as dt
import json
import os
import time

import pandas as pd
import requests

from .config import DATA, scrub

BASE = "https://openapivts.koreainvestment.com:29443"      # PAPER (mock investing) only
ALLOWED = {"/oauth2/tokenP", "/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice"}
STATUS = DATA / "kis_status.json"


def _req(method, path, **kw):
    if path not in ALLOWED:
        raise RuntimeError("path not allowed: " + path)
    return requests.request(method, BASE + path, timeout=20, **kw)


_TOKEN = {}


def _creds():
    key, sec = os.environ.get("HANTOO_TEST_KEY"), os.environ.get("HANTOO_TEST_SECRET")
    if not key or not sec:
        raise RuntimeError("HANTOO_TEST_KEY/SECRET not present in this container")
    return key, sec


def get_token():
    """One token per process (issuance is limited to 1/min). Held in memory only, never written."""
    if "t" not in _TOKEN:
        key, sec = _creds()
        r = _req("POST", "/oauth2/tokenP", json={"grant_type": "client_credentials", "appkey": key, "appsecret": sec})
        if r.status_code != 200:
            raise RuntimeError("token HTTP %s: %s" % (r.status_code, scrub(r.text, 300)))
        t = r.json().get("access_token")
        if not t:
            raise RuntimeError("token response has no access_token: " + scrub(r.text, 300))
        _TOKEN["t"] = t
    return _TOKEN["t"]


def _get_chart(hdr, q, tries=4):
    for i in range(tries):
        time.sleep(0.8)  # paper API: ~2 req/s limit
        r = _req("GET", "/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice", headers=hdr, params=q)
        if "EGW00201" in r.text and i < tries - 1:   # per-second rate limit
            time.sleep(1.5 * (i + 1))
            continue
        return r
    return r


def fetch_daily(code, days=400):
    key, sec = _creds()
    token = get_token()
    hdr = {"authorization": "Bearer " + token, "appkey": key, "appsecret": sec,
           "tr_id": "FHKST03010100", "custtype": "P"}
    end = dt.date.today()
    rows = []
    while len(rows) < days:
        start = end - dt.timedelta(days=140)
        q = {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": code, "FID_INPUT_DATE_1": start.strftime("%Y%m%d"),
             "FID_INPUT_DATE_2": end.strftime("%Y%m%d"), "FID_PERIOD_DIV_CODE": "D", "FID_ORG_ADJ_PRC": "0"}
        r = _get_chart(hdr, q)
        j = r.json() if r.status_code == 200 else {}
        if r.status_code != 200 or j.get("rt_cd") != "0":
            raise RuntimeError("chart HTTP %s rt_cd=%s msg_cd=%s msg=%s" % (
                r.status_code, j.get("rt_cd"), j.get("msg_cd"), scrub(j.get("msg1", r.text), 200)))
        part = j.get("output2") or []
        part = [p for p in part if p.get("stck_bsop_date")]
        if not part:
            break
        rows.extend(part)
        oldest = min(p["stck_bsop_date"] for p in part)
        end = dt.datetime.strptime(oldest, "%Y%m%d").date() - dt.timedelta(days=1)
    if not rows:
        raise RuntimeError("no rows returned")
    df = pd.DataFrame(rows)
    df.index = pd.to_datetime(df["stck_bsop_date"], utc=True)
    df.index.name = "ts"
    df = df.rename(columns={"stck_oprc": "open", "stck_hgpr": "high", "stck_lwpr": "low",
                            "stck_clpr": "close", "acml_vol": "volume"})[["open", "high", "low", "close", "volume"]]
    df = df.astype(float).sort_index()
    return df[~df.index.duplicated()]


def write_status(ok, detail):
    DATA.mkdir(parents=True, exist_ok=True)
    STATUS.write_text(json.dumps({"ok": ok, "endpoint": BASE, "detail": detail,
                                  "at": dt.datetime.now(dt.timezone.utc).isoformat()}, ensure_ascii=False, indent=1))
