"""Fetch SEC XBRL companyfacts JSON for every resolved CIK (one call per company = full history). Point-in-time
correctness and concept taxonomy are documented in PREREG_trader_skill_v1.md. Read-only network use.
"""
import gzip
import json
import os
import sys
import time
import urllib.error
import urllib.request

UA = os.environ.get("SEC_USER_AGENT", "oracle-research research@localhost")
URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK%s.json"
PAUSE = 0.25


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "gzip"})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = r.read()
        if r.headers.get("Content-Encoding") == "gzip":
            data = gzip.decompress(data)
        return data


def main():
    cik_map_path, cache_dir = sys.argv[1], sys.argv[2]
    cik_map = json.loads(open(cik_map_path).read())
    os.makedirs(cache_dir, exist_ok=True)
    ciks = {}
    for sym, v in cik_map.items():
        if v and "cik" in v:
            ciks.setdefault(v["cik"], []).append(sym)
    todo = [c for c in ciks if not os.path.exists(os.path.join(cache_dir, c + ".json"))]
    print("unique_ciks=%d already_cached=%d todo=%d" % (len(ciks), len(ciks) - len(todo), len(todo)), flush=True)
    errs = {}
    for i, cik in enumerate(todo):
        time.sleep(PAUSE)
        try:
            body = get(URL % cik.zfill(10))
            open(os.path.join(cache_dir, cik + ".json"), "wb").write(body)
        except urllib.error.HTTPError as e:
            errs[cik] = "HTTP %s (%s)" % (e.code, ",".join(ciks[cik]))
        except Exception as e:
            errs[cik] = "%s: %s (%s)" % (type(e).__name__, str(e)[:120], ",".join(ciks[cik]))
        if (i + 1) % 50 == 0 or (i + 1) == len(todo):
            print("%d/%d  errs_so_far=%d" % (i + 1, len(todo), len(errs)), flush=True)
    open(os.path.join(cache_dir, "_errors.json"), "w").write(json.dumps(errs, indent=1))
    print("done. errors=%d" % len(errs))


if __name__ == "__main__":
    main()
