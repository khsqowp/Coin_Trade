import csv, numpy as np
import search_rb1000_kr as m
import search_kr_r14_batch as base
from search_equities_r5 import load_membership
from data_quality import filter_equity_bars
membership = load_membership(base.MEMBERSHIP_PATH)
rows = {r["symbol"].strip(): r for r in csv.DictReader(base.UNIVERSE_PATH.open(newline="", encoding="utf-8-sig"))}
for sym in ("004230", "047710"):
    row = rows[sym]
    frame, _ = base._load_symbol(row["daily_path"], sym)
    clean, _ = filter_equity_bars(frame, sym)
    c = clean["close"].astype(float).to_numpy()
    jumps = m._jump_indices(c)
    print(sym, "n", len(c), "raw jumps", [(int(k), round(c[k]/c[k-1],4), m.split_ratio(c[k]/c[k-1]), round(m.limit_threshold(c[k-1]),3)) for k in jumps])
    print("   tail closes", c[-12:].tolist())
    print("   tail dates", clean["open_time"].to_numpy()[-12:].tolist()[:3])
