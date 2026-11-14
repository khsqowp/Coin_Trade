import sys, json
sys.path.insert(0, "/app/src")
from tp import llm
for m in ["claude-haiku-5-5","claude-sonnet-5-5","deepseek-flash","gpt-5.4-mini"]:
    try:
        r = llm.chat(m, "Reply in JSON.", [{"role":"user","content":'Return {"ok":true,"n":2+3} only.'}], max_tokens=60, json_mode=True, retries=0, role="smoke", purpose="param-check")
        print(m, "OK", repr(r["text"][:60]), r["in_tok"], r["out_tok"], round(r["cost"],6), round(r["latency"],1))
    except Exception as e:
        print(m, "FAIL", str(e)[:300])
