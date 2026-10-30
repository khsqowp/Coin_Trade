"""R2C step 1: enumerate every USDT-M symbol that ever has monthly klines on data.binance.vision (public S3 listing; includes delisted).
Output: data/symbols_all.json  {symbol: [first_month, last_month, n_months]} for 1d klines. No keys."""
import json, re, sys, urllib.request, urllib.parse, xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
B = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision"
NS = {"s": "http://s3.amazonaws.com/doc/2006-03-01/"}
def ls(prefix, delim="/"):
    keys, pre, marker = [], [], ""
    while True:
        q = {"prefix": prefix, "max-keys": "1000"}
        if delim: q["delimiter"] = delim
        if marker: q["marker"] = marker
        for t in range(5):
            try:
                x = urllib.request.urlopen(B + "?" + urllib.parse.urlencode(q), timeout=60).read(); break
            except Exception as e:
                if t == 4: raise
        r = ET.fromstring(x)
        keys += [k.find("s:Key", NS).text for k in r.findall("s:Contents", NS)]
        pre += [k.find("s:Prefix", NS).text for k in r.findall("s:CommonPrefixes", NS)]
        if r.find("s:IsTruncated", NS).text != "true": break
        nm = r.find("s:NextMarker", NS)
        marker = nm.text if nm is not None else (keys[-1] if keys else pre[-1])
    return keys, pre
if __name__ == "__main__":
    _, pre = ls("data/futures/um/monthly/klines/")
    syms = sorted(p.split("/")[-2] for p in pre)
    print("all symbol dirs", len(syms))
    def one(s):
        k, _ = ls(f"data/futures/um/monthly/klines/{s}/1d/", None)
        m = sorted(re.findall(r"-(\d{4}-\d{2})\.zip$", x)[0] for x in k if x.endswith(".zip"))
        return s, m
    out = {}
    with ThreadPoolExecutor(16) as ex:
        for s, m in ex.map(one, syms):
            if m: out[s] = [m[0], m[-1], len(m)]
    json.dump(out, open("data/symbols_all.json", "w"), indent=0, sort_keys=True)
    print("with 1d data", len(out))
