"""Pre-registration smoke: loads the real TRAIN panel, builds units for all 200 configs.
Prints only exception status, unit counts and data-quality counts. No returns or gate metrics."""
import csv, time, traceback
from collections import Counter
import numpy as np
import search_rb1000_kr as m
import search_kr_r14_batch as base
from search_equities_r5 import load_membership

t0 = time.time()
configs = m.build_configs()
rows = list(csv.DictReader(base.UNIVERSE_PATH.open(newline="", encoding="utf-8-sig")))
membership = load_membership(base.MEMBERSHIP_PATH)
records, acct = [], {}
for row in rows:
    rec, info = m._load_stock(row, membership)
    acct[row["symbol"].strip()] = info
    if rec is not None:
        records.append(rec)
idx = {code: m._load_index_code(code) for code in ("KS11", "KQ11", "KS200")}
P = m.Panel(records, idx)
m.STATE = P
print("quality", m.summarize_quality(acct, records))
print("grid T", P.T, "stocks", P.S, "load_s", round(time.time() - t0, 1))
fails = []
per_family = {}
for i, cfg in enumerate(configs):
    try:
        units, counts = m.build_units(cfg, 0, 1.0, P)
        fam = cfg["family"]
        agg = per_family.setdefault(fam, Counter())
        agg["configs"] += 1
        agg["units"] += len(units)
        agg["min_units_cfg"] = min(agg.get("min_units_cfg", 10**9), len(units))
        agg["max_units_cfg"] = max(agg.get("max_units_cfg", 0), len(units))
    except Exception as exc:
        fails.append((i, cfg, f"{type(exc).__name__}: {exc}", traceback.format_exc(limit=3)[-600:]))
print("failures", len(fails))
for f in fails[:5]:
    print(f)
for fam, agg in per_family.items():
    print(fam, dict(agg))
print("elapsed", round(time.time() - t0, 1))
