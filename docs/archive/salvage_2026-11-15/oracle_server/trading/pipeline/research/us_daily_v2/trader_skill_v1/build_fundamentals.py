"""Build point-in-time fundamental factor series (one sparse row per known quarter, dated at its SEC filing
visibility date) from cached SEC XBRL companyfacts JSON. See PREREG_trader_skill_v1.md for concept taxonomy,
point-in-time rule and factor formulas. No network use (reads the on-disk cache only).
"""
import json
import os
import re
import sys

import pandas as pd

CONCEPTS = {
    "revenue": ["RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues",
                "RevenuesNetOfInterestExpense", "RevenueFromContractWithCustomerIncludingAssessedTax",
                "SalesRevenueNet", "SalesRevenueGoodsNet", "SalesRevenueServicesNet"],
    "cost_of_revenue": ["CostOfGoodsAndServicesSold", "CostOfRevenue", "CostOfGoodsSold"],
    "gross_profit": ["GrossProfit"],
    "eps_diluted": ["EarningsPerShareDiluted", "EarningsPerShareBasicAndDiluted"],
}
FRAME_RE = re.compile(r"^CY(\d{4})Q([1-4])$")


def quarterly_rows(node):
    """node = companyfacts['facts']['us-gaap'][tag]. Returns {(year,q): (val, filed)} picking, for each frame,
    the row with the EARLIEST filed date (first public disclosure; avoids using a later restatement that was
    not knowable at that earlier date)."""
    out = {}
    units = node.get("units", {})
    unit = "USD" if "USD" in units else ("USD/shares" if "USD/shares" in units else next(iter(units), None))
    for r in units.get(unit, []) if unit else []:
        frame = r.get("frame")
        if not frame:
            continue
        m = FRAME_RE.match(frame)
        if not m or r.get("val") is None or not r.get("filed"):
            continue
        key = (int(m.group(1)), int(m.group(2)))
        cur = out.get(key)
        if cur is None or r["filed"] < cur[1]:
            out[key] = (r["val"], r["filed"])
    return out


def first_available(facts, tags):
    """Merge quarterly facts across every tag in priority order (not just the first with enough rows): many
    companies switched their primary revenue/EPS tag around the ASC 606 transition (fiscal years beginning after
    2017-12-15), so a company's pre-2018 history often lives under an older tag (e.g. SalesRevenueNet) and its
    2018+ history under a newer one (e.g. RevenueFromContractWithCustomerExcludingAssessedTax). Picking only the
    first tag with >= 8 rows silently truncated history for exactly these companies (found via a GME audit case:
    PIT spell 2007-2016, but the newer tag alone only had data from 2019). On a frame-key conflict between tags,
    the earlier tag in the priority list wins (first-seen keeps its value)."""
    merged = {}
    for t in tags:
        node = facts.get(t)
        if not node:
            continue
        for key, val in quarterly_rows(node).items():
            merged.setdefault(key, val)
    return merged


def build_one(companyfacts):
    facts = (companyfacts.get("facts") or {}).get("us-gaap") or {}
    rev = first_available(facts, CONCEPTS["revenue"])
    cor = first_available(facts, CONCEPTS["cost_of_revenue"])
    gp = first_available(facts, CONCEPTS["gross_profit"])
    eps = first_available(facts, CONCEPTS["eps_diluted"])
    quarters = sorted(set(rev) | set(gp) | set(cor) | set(eps))
    rows = []
    eps_hist = []   # (key, filed, val) in filed order for trailing-4 sum
    for key in sorted(set(rev) | set(eps)):
        if key in eps:
            eps_hist.append((key, eps[key][1], eps[key][0]))
    eps_hist.sort(key=lambda x: x[1])
    for key in quarters:
        y, q = key
        rv, rv_f = rev.get(key, (None, None))
        prior = rev.get((y - 1, q))
        rev_growth = None
        if rv is not None and prior and prior[0]:
            rev_growth = rv / prior[0] - 1
        margin, margin_f = None, rv_f
        if rv:
            if key in gp and gp[key][0] is not None:
                margin = gp[key][0] / rv
                margin_f = max(rv_f or "", gp[key][1]) if rv_f else gp[key][1]
            elif key in cor and cor[key][0] is not None:
                margin = 1 - cor[key][0] / rv
                margin_f = max(rv_f or "", cor[key][1]) if rv_f else cor[key][1]
        prior_margin = None
        py = (y - 1, q)
        if py in rev and rev[py][0]:
            prv = rev[py][0]
            if py in gp and gp[py][0] is not None:
                prior_margin = gp[py][0] / prv
            elif py in cor and cor[py][0] is not None:
                prior_margin = 1 - cor[py][0] / prv
        margin_chg = (margin - prior_margin) if (margin is not None and prior_margin is not None) else None
        # trailing-4 EPS sum known as of this quarter's filed date: the 4 most-recent eps_hist entries filed
        # on/before this quarter's own filed date (rv_f), in filed order.
        asof = rv_f or margin_f
        trailing_eps = None
        if asof:
            avail = [v for k, f, v in eps_hist if f <= asof]
            if len(avail) >= 4:
                trailing_eps = sum(avail[-4:])
        filed = max(x for x in (rv_f, margin_f, asof) if x) if (rv_f or margin_f or asof) else None
        if filed is None:
            continue
        # fixed, pre-decided sanity bounds (data-quality gate, not a performance choice): mixing two different
        # revenue-concept tags for the same company (e.g. a bank's "Revenues" vs "RevenuesNetOfInterestExpense")
        # or a one-off tagging error can otherwise produce implausible outliers (seen: STI rev_growth_yoy=30.2,
        # gross_margin=-1.88) that would dominate a top-50 cross-sectional rank. Out-of-bounds -> excluded (None),
        # not clipped, so they do not land at the boundary and still dominate the ranking.
        if rev_growth is not None and not (-0.95 <= rev_growth <= 10.0):
            rev_growth = None
        if margin is not None and not (-0.5 <= margin <= 1.0):
            margin = None
        if margin_chg is not None and not (-1.0 <= margin_chg <= 1.0):
            margin_chg = None
        rows.append({"year": y, "q": q, "filed": filed, "rev_growth_yoy": rev_growth,
                     "gross_margin": margin, "margin_chg": margin_chg, "trailing_eps": trailing_eps})
    return rows


def main():
    cik_map_path, cache_dir, out_path = sys.argv[1], sys.argv[2], sys.argv[3]
    cik_map = json.loads(open(cik_map_path).read())
    out = {}
    n_ok, n_fail = 0, 0
    for sym, v in cik_map.items():
        if not (v and "cik" in v):
            continue
        p = os.path.join(cache_dir, v["cik"] + ".json")
        if not os.path.exists(p):
            n_fail += 1
            continue
        try:
            cf = json.loads(open(p).read())
            rows = build_one(cf)
        except Exception as e:
            n_fail += 1
            print("fail", sym, type(e).__name__, str(e)[:150])
            continue
        if rows:
            out[sym] = rows
            n_ok += 1
        else:
            n_fail += 1
    print("symbols_with_factor_rows=%d  symbols_failed_or_empty=%d" % (n_ok, n_fail))
    with open(out_path, "w") as fh:
        json.dump(out, fh)
    # quick sanity print
    import random
    sample = random.sample(sorted(out), min(3, len(out)))
    for s in sample:
        print(s, out[s][-3:])


if __name__ == "__main__":
    main()
