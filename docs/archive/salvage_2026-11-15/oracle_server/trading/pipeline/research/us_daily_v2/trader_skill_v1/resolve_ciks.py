"""Resolve CIK for every PIT symbol via EDGAR full-text search on the vendor longName (company_tickers.json and
www.sec.gov/cgi-bin/browse-edgar are blocked for this server's IP; data.sec.gov and efts.sec.gov are not).
Method and adversarial-case check are in PREREG_trader_skill_v1.md. Writes sym -> {cik, matched_name} JSON, and a
separate list of unresolved symbols. Read-only network use (SEC EDGAR full text search).
"""
import gzip
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

UA = os.environ.get("SEC_USER_AGENT", "oracle-research research@localhost")
SEARCH = "https://efts.sec.gov/LATEST/search-index?q=%s&forms=10-K"
PAUSE = 0.35


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "gzip"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = r.read()
        if r.headers.get("Content-Encoding") == "gzip":
            data = gzip.decompress(data)
        return json.loads(data)


def norm_ticker(t):
    return t.replace(".", "-").upper()


def resolve(sym, longname):
    if not longname:
        return None
    q = urllib.parse.quote('"%s"' % longname)
    try:
        j = get(SEARCH % q)
    except Exception as e:
        return {"error": "%s: %s" % (type(e).__name__, str(e)[:150])}
    hits = j.get("hits", {}).get("hits", [])
    if not hits:
        return None
    for h in hits[:5]:
        dn = h.get("_source", {}).get("display_names", [])
        for name in dn:
            m = re.search(r"\(([^)]*)\)\s*\(CIK (\d+)\)", name)
            if not m:
                continue
            tickers = [norm_ticker(x.strip()) for x in m.group(1).split(",")]
            if norm_ticker(sym) in tickers:
                return {"cik": m.group(2), "matched_name": name}
    return None


def main():
    data_dir = sys.argv[1] if len(sys.argv) > 1 else "data/us_daily"
    out_path = sys.argv[2] if len(sys.argv) > 2 else "cik_map.json"
    syms = json.loads(open(sys.argv[3]).read()) if len(sys.argv) > 3 else None
    if syms is None:
        syms = sorted(s[:-10] for s in os.listdir(data_dir) if s.endswith(".meta.json"))
    out = {}
    if os.path.exists(out_path):
        out = json.loads(open(out_path).read())
    todo = [s for s in syms if s not in out]
    print("total=%d already_done=%d todo=%d" % (len(syms), len(out), len(todo)), flush=True)
    for i, sym in enumerate(todo):
        p = os.path.join(data_dir, sym + ".meta.json")
        try:
            meta = json.loads(open(p).read())
        except FileNotFoundError:
            out[sym] = {"error": "no meta file"}
            continue
        longname = (meta.get("vendor") or {}).get("longName")
        time.sleep(PAUSE)
        res = resolve(sym, longname)
        out[sym] = res if res is not None else {"unresolved": True, "longname": longname}
        if (i + 1) % 25 == 0 or (i + 1) == len(todo):
            print("%d/%d %s -> %s" % (i + 1, len(todo), sym, out[sym]), flush=True)
            open(out_path, "w").write(json.dumps(out, indent=1))
    open(out_path, "w").write(json.dumps(out, indent=1))
    n_ok = sum(1 for v in out.values() if v and "cik" in v)
    print("done. resolved=%d / %d" % (n_ok, len(out)))


if __name__ == "__main__":
    main()
