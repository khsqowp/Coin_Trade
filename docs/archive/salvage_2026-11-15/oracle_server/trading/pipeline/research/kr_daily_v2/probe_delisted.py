import json, sys
from tp import kis
key, sec = kis._creds(); tok = kis.get_token()
hdr = {"authorization": "Bearer " + tok, "appkey": key, "appsecret": sec, "tr_id": "FHKST03010100", "custtype": "P"}
for c, a, b in [("053000","20140601","20141031"),("000830","20150301","20150701"),("005110","20260601","20260930"),("134780","20200101","20200501"),("026180","20190101","20190501"),("181980","20141101","20150301"),("0220W0","20261001","20261103")]:
    q = {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": c, "FID_INPUT_DATE_1": a, "FID_INPUT_DATE_2": b, "FID_PERIOD_DIV_CODE": "D", "FID_ORG_ADJ_PRC": "0"}
    r = kis._get_chart(hdr, q); j = r.json() if r.status_code == 200 else {}
    rows = [p for p in (j.get("output2") or []) if p.get("stck_bsop_date")]
    print(c, r.status_code, j.get("rt_cd"), j.get("msg1","")[:60], "rows", len(rows), (rows[-1]["stck_bsop_date"], rows[0]["stck_bsop_date"], rows[0]["stck_clpr"]) if rows else "", (j.get("output1") or {}).get("hts_kor_isnm"), flush=True)
