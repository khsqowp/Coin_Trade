import os, requests, re
def models(name, url, hdr, key):
    try:
        r = requests.get(url, headers=hdr, timeout=30)
        ids = []
        j = r.json() if r.headers.get("content-type","").startswith("application/json") else {}
        for m in j.get("data", j.get("models", [])):
            ids.append(m.get("id") or m.get("name"))
        print(name, r.status_code, len(ids))
        return ids
    except Exception as e:
        print(name, "ERR", type(e).__name__); return []
E = os.environ
a = models("anthropic","https://api.anthropic.com/v1/models?limit=100",{"x-api-key":E["ANTHROPIC_API_KEY"],"anthropic-version":"2023-06-01"},0)
print([x for x in a if re.search("haiku|sonnet",x)])
d = models("deepseek","https://api.deepseek.com/models",{"Authorization":"Bearer "+E["DEEPSEEK_API_KEY"]},0); print(d)
o = models("openai","https://api.openai.com/v1/models",{"Authorization":"Bearer "+E["CHATGPT_API_KEY"]},0)
print(sorted(x for x in o if re.match(r"gpt-(5\.4|5\.6|6)",x) and "luna" not in x and "audio" not in x and "realtime" not in x and "image" not in x)[:40])
g = models("gemini","https://generativelanguage.googleapis.com/v1beta/models?pageSize=200",{"x-goog-api-key":E["GEMINI_API_KEY"]},0)
print([x for x in g if re.search(r"3\.[5-9]-flash|3\.1-flash-lite",x) and "tts" not in x and "live" not in x and "image" not in x][:20])
for u in ["https://api.binance.com/api/v3/ping","https://openapivts.koreainvestment.com:29443/"]:
    try: print(u, requests.get(u,timeout=15).status_code)
    except Exception as e: print(u,"ERR",type(e).__name__)
