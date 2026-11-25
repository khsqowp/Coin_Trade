import csv, json, sys, statistics as st
from collections import Counter, defaultdict
csv.field_size_limit(sys.maxsize)
path = sys.argv[1]
rows = list(csv.DictReader(open(path, encoding="utf-8")))
def jload(v):
    try:
        return json.loads(v) if v not in ("", None) else None
    except Exception:
        return None
def f(v):
    try:
        return float(v) if v not in ("", None, "None") else None
    except Exception:
        return None
print("rows", len(rows), "status", Counter(r["status"] for r in rows))
fam = defaultdict(list)
for r in rows:
    fam[r["family"]].append(r)
hdr = "family n scored trades_med exp_pos core_pass bonf_pass delay_pass cost2_pass cluster_pass yearly_pass top3_pass candidates median_exp_bps"
print(hdr)
for family, rs in fam.items():
    sc = [r for r in rs if r["status"] == "scored"]
    def cnt(key):
        return sum(1 for r in sc if (jload(r.get("core_gate")) or {}) and r["passes_core"] in ("True", True) and False) if False else None
    exp = [f(r["expectancy_bps"]) for r in sc if f(r["expectancy_bps"]) is not None]
    supp = [jload(r["supplementary"]) or {} for r in sc]
    tm = [f(r["trades"]) for r in sc]
    line = [family, len(rs), len(sc), st.median(tm) if tm else None,
            sum(1 for e in exp if e > 0),
            sum(1 for r in sc if r["passes_core"] == "True"),
            sum(1 for r in sc if r["passes_bonferroni"] == "True"),
            sum(1 for s in supp if (s.get("delay_1bar") or {}).get("pass") is True),
            sum(1 for s in supp if (s.get("cost_2x") or {}).get("pass") is True),
            sum(1 for s in supp if (s.get("cluster_p") or {}).get("pass") is True),
            sum(1 for s in supp if (s.get("yearly") or {}).get("pass") is True),
            sum(1 for s in supp if (s.get("top3_excluded") or {}).get("pass") is True),
            sum(1 for r in sc if r["candidate"] == "True"),
            round(st.median(exp), 2) if exp else None]
    print(line)
print("\nTOTAL candidates:", sum(1 for r in rows if r["candidate"] == "True"))
print("TOTAL core pass:", sum(1 for r in rows if r.get("passes_core") == "True"),
      " bonf pass:", sum(1 for r in rows if r.get("passes_bonferroni") == "True"))
