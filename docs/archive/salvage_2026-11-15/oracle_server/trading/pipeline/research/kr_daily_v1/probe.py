"""Availability probe only: listing name + whether daily history exists at 2008 / 2012 / 2016 windows. No returns computed."""
import json, sys
from tp import kis
codes = sys.argv[1].split(",")
key, sec = kis._creds(); tok = kis.get_token()
hdr = {"authorization": "Bearer " + tok, "appkey": key, "appsecret": sec, "tr_id": "FHKST03010100", "custtype": "P"}
out = {}
for c in codes:
    rec = {}
    for lab, a, b in [("now", "20261001", "20261030"), ("y2008", "20080101", "20080301"), ("y2012", "20120101", "20120301"), ("y2016", "20160101", "20160301")]:
        q = {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": c, "FID_INPUT_DATE_1": a, "FID_INPUT_DATE_2": b, "FID_PERIOD_DIV_CODE": "D", "FID_ORG_ADJ_PRC": "0"}
        r = kis._get_chart(hdr, q); j = r.json() if r.status_code == 200 else {}
        rows = [p for p in (j.get("output2") or []) if p.get("stck_bsop_date")]
        if lab == "now":
            o1 = j.get("output1") or {}
            rec["name"] = o1.get("hts_kor_isnm"); rec["mcap_now_100m"] = o1.get("hts_avls"); rec["vol_now"] = o1.get("acml_vol"); rec["tr_pbmn_now"] = o1.get("acml_tr_pbmn")
        rec[lab] = len(rows)
    out[c] = rec
    print(c, json.dumps(rec, ensure_ascii=False), flush=True)
