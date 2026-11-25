#!/usr/bin/env python3
"""EXPLORATORY SCREEN ONLY -- supplementary side split for the lane G top-20.

Re-runs the same signals/engine from screen.py and splits each pooled result into
long-only and short-only trades, so a bullish-TRAIN long bias is visible.
Writes SIDE_SPLIT_TOP20.csv into this directory. Not part of the formal track.
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import screen as sc  # noqa: E402

TOP_N = 20


def main():
    res = pd.read_csv(HERE / "RESULTS.csv")
    ideas = {i["idea_id"]: i for i in sc.build_catalog()}
    top = (res[res.status == "SCORED"].sort_values("composite_score", ascending=False)
           .head(TOP_N)["idea_id"].tolist())
    raw = {tf: sc.load_tf(tf) for tf in sc.LOAD_TFS}
    rows = []
    for iid in top:
        idea = ideas[iid]
        trig = idea["trig_tf"]
        need = ["1h", "4h"] if trig == "1h" else ["15m", "1h", "4h"]
        pooled = {"long": ([], []), "short": ([], [])}
        for sym in sorted(set.intersection(*[set(raw[tf]) for tf in need])):
            frames = sc.build_frames(raw, sym)
            if frames is None:
                continue
            M = sc.context(frames, trig)
            sig = sc.SIG_FN[idea["family"]](M, trig, idea["params"])
            H = int(idea["params"]["H"])
            k = float(idea["params"].get("k", 0))
            for side, val in (("long", 1), ("short", -1)):
                s = np.where(sig == val, sig, 0).astype(np.int8)
                r, t = sc.simulate(s, M, trig, H, k)
                if len(r):
                    pooled[side][0].append(r)
                    pooled[side][1].append(t)
        row = {"idea_id": iid, "name": idea["name"]}
        for side in ("long", "short"):
            rs = np.concatenate(pooled[side][0]) if pooled[side][0] else np.array([])
            ts = np.concatenate(pooled[side][1]) if pooled[side][1] else np.array([])
            m = sc.metrics(rs, ts)
            row[f"{side}_n"] = m["n_trades"]
            row[f"{side}_ev_bps"] = round(m["expectancy_bps"], 2) if m["n_trades"] else ""
            row[f"{side}_pf"] = round(m["profit_factor"], 3) if m["n_trades"] and np.isfinite(m["profit_factor"]) else ""
        rows.append(row)
        print(row["idea_id"], row["long_n"], row["long_ev_bps"], row["short_n"], row["short_ev_bps"], flush=True)
    with open(HERE / "SIDE_SPLIT_TOP20.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    main()
