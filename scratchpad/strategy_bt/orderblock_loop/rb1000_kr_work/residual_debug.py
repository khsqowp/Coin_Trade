import csv, numpy as np
import search_rb1000_kr as m
import search_kr_r14_batch as base
from search_equities_r5 import load_membership
rows = list(csv.DictReader(base.UNIVERSE_PATH.open(newline="", encoding="utf-8-sig")))
membership = load_membership(base.MEMBERSHIP_PATH)
for row in rows:
    rec, info = m._load_stock(row, membership)
    if "adjust" in info and info["adjust"]["residual_jumps"]:
        print("STATUS", row["symbol"], info["status"], info["adjust"])
        import search_rb1000_kr as mm
        t, o, h, l, c, v, rep = mm.adjust_corporate_actions(*[np.asarray(x) for x in ()]) if False else (None,)*7
        c = rec["c"] if rec is not None else None
        if c is None:
            continue
        j = m._jump_indices(c)
        for k in j:
            print(row["symbol"], "idx", k, "prev", c[k-1], "cur", c[k], "ratio", round(c[k]/c[k-1],4), "thr", round(m.limit_threshold(c[k-1]),4), "split_n", m.split_ratio(c[k]/c[k-1]), "n", len(c))
