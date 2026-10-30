"""BACKTESTER-C analysis: tables + verdicts from results.json / results_r.npz (prereg rules). stdout only."""
from __future__ import annotations
import json, os
import numpy as np
from app.rs_lev_c_run import SETS, LADDER, boot_diff, kendall, MONN

D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "docs", "research", "lev_loop", "C")
R = json.load(open(os.path.join(D, "results.json")))
Z = np.load(os.path.join(D, "results_r.npz"))
DS = R["meta"]["d_start"]; ND = R["meta"]["nd"]
S5 = list(SETS)
LAD = [f"L{l:g}x0.95" for l in LADDER]
ALL = S5 + LAD
LABEL = {k: f"{v[0]:g}x{v[1]:g}" for k, v in SETS.items()}
for l in LADDER:
    LABEL[f"L{l:g}x0.95"] = f"{l:g}x0.95"
pct = lambda a, p: float(np.percentile(a, p))


def pagg(u, key):
    return float(np.mean([p[key] for p in u["phases"]]))


def breach(x, m):
    """path-level breach for monitor m (0..5); tier also counts primary liquidation"""
    if m == 0 and x["liq"]:
        return True
    return x["mon_first"][m] >= 0


def rarr(key):
    return Z[key].astype(np.float64)


print("=" * 100); print("TRIALS", R["trials"], "U-keys", len(R["U"]))
print("fund window", R["meta"]["fund_window"], "wick day", R["meta"]["wick_day"])
w = R["meta"]["wick"]; print("wick: median %.2f min %.2f max %.2f" % (np.median(list(w.values())), min(w.values()), max(w.values())))

# ------------------------------------------------------------------ U1 / U2
for U in ("U1", "U2"):
    print("=" * 100); print(U, "(3-phase mean; tier-MM hourly liquidation active)")
    print("%-9s %6s %6s %6s %7s %7s %7s %6s %4s %7s %7s" % ("cfg", "g", "g_IS", "g_OOS", "CAGR", "MDD", "iMDD", "kills", "liq", "minbuf", "TWmin"))
    for c in ALL:
        u = R["U"][U][c]
        print("%-9s %6.3f %6.3f %6.3f %6.1f%% %6.1f%% %6.1f%% %6.1f %4d %7.3f %7.2f" % (
            LABEL[c], pagg(u, "g"), pagg(u, "g_is"), pagg(u, "g_oos"), 100 * pagg(u, "cagr"), 100 * pagg(u, "mdd"), 100 * pagg(u, "imdd"),
            pagg(u, "kills"), sum(p["liq"] for p in u["phases"]), min(p["mon_min"][0] for p in u["phases"]), min(p["tw"] for p in u["phases"])))

# ------------------------------------------------------------------ bootstrap vs S0 (U1, U2), block sensitivity
BOOT = {}
for U in ("U1", "U2"):
    print("=" * 100); print("BOOTSTRAP", U, "g_s - g_S0 (annualised log growth), block 15d, B=2000; Bonferroni m=4 CI [0.625,99.375]")
    r0 = rarr(f"{U}|S0")
    for c in S5[1:]:
        rd = rarr(f"{U}|{c}") - r0
        b = boot_diff(rd, DS, ND, block=15)
        b10 = boot_diff(rd, DS, ND, block=10); b20 = boot_diff(rd, DS, ND, block=20)
        BOOT[(U, c)] = b
        print("%-6s point %+6.3f se %5.3f  95%% [%+6.3f,%+6.3f]  Bonf [%+6.3f,%+6.3f]  blk10 se %5.3f blk20 se %5.3f  haircut(pt-1.163*se) %+6.3f" % (
            LABEL[c], b["point"], b["se"], b["lo95"], b["hi95"], b["lo_bonf"], b["hi_bonf"], b10["se"], b20["se"], b["point"] - 1.163 * b["se"]))

# ------------------------------------------------------------------ universe persistence
keys = ["U1", "U2"] + [f"U3_{k:02d}" for k in range(30)]
print("=" * 100); print("PERSISTENCE across 32 universes (U1,U2,30 random subsets), vs S0=4x0.95")
G = {c: {w: np.array([pagg(R["U"][u][c], k) for u in keys]) for w, k in (("full", "g"), ("is", "g_is"), ("oos", "g_oos"))} for c in ALL}
for c in S5[1:] + LAD:
    pf = np.mean(G[c]["full"] > G["S0"]["full"]); pi = np.mean(G[c]["is"] > G["S0"]["is"]); po = np.mean(G[c]["oos"] > G["S0"]["oos"])
    md = np.median(G[c]["full"] - G["S0"]["full"])
    liqn = sum(sum(p["liq"] for p in R["U"][u][c]["phases"]) for u in keys)
    print("%-9s P(g>S0) full %.2f IS %.2f OOS %.2f | median dg %+6.3f | liq-paths %d/%d" % (LABEL[c], pf, pi, po, md, liqn, 3 * len(keys)))
# ordering
base_rank = np.array([G[c]["full"][0] for c in S5])
taus = []; top1 = {c: 0 for c in S5}
for k in range(len(keys)):
    v = np.array([G[c]["full"][k] for c in S5]); taus.append(kendall(v, base_rank)); top1[S5[int(v.argmax())]] += 1
print("Kendall tau vs U1 ordering over 32 universes: median %.2f  p10 %.2f  min %.2f" % (np.median(taus), pct(taus, 10), min(taus)))
print("top-1 frequency among S0..S4:", {LABEL[c]: top1[c] for c in S5})
print("mean g across universes (S0..S4):", {LABEL[c]: round(float(G[c]["full"].mean()), 3) for c in S5})
print("U3 only (30 subsets) median g:", {LABEL[c]: round(float(np.median(G[c]["full"][2:])), 3) for c in S5}, "idle share of S0 (flat days) median %.3f" % np.median([np.mean([p["flat"] for p in R["U"][u]["S0"]["phases"]]) for u in keys[2:]]))
# per-subset bootstrap persistence (Bonferroni lower>0)
print("subset-level CI: #subsets where Bonf CI lower>0 / upper<0")
for c in S5[1:]:
    lo = hi = 0
    for u in keys:
        rd = rarr(f"{u}|{c}") - rarr(f"{u}|S0"); b = boot_diff(rd, DS, ND, B=500)
        lo += b["lo_bonf"] > 0; hi += b["hi_bonf"] < 0
    print("  %-6s lower>0: %d/32  upper<0: %d/32" % (LABEL[c], lo, hi))

# ------------------------------------------------------------------ delisting stress
print("=" * 100); print("U4 DELISTING STRESS (20 seeds x 3 phases; 15 events/seed, long -90% / short +100%)")
for c in S5 + LAD:
    gs = np.array([pagg(R["U"][f"U4_{s:02d}"][c], "g") for s in range(1, 21)])
    liqn = sum(sum(p["liq"] for p in R["U"][f"U4_{s:02d}"][c]["phases"]) for s in range(1, 21))
    bre = sum(sum(breach(p, 0) for p in R["U"][f"U4_{s:02d}"][c]["phases"]) for s in range(1, 21))
    g0 = np.array([pagg(R["U"][f"U4_{s:02d}"]["S0"], "g") for s in range(1, 21)])
    tw = np.array([np.mean([p["tw"] for p in R["U"][f"U4_{s:02d}"][c]["phases"]]) for s in range(1, 21)])
    print("%-9s median g %+6.2f p10 %+6.2f | P(g>S0) %.2f | median TW %.2f p10 TW %.2f | tier-breach paths %d/60 | min buf %.3f" % (
        LABEL[c], np.median(gs), pct(gs, 10), np.mean(gs > g0), np.median(tw), pct(tw, 10), bre,
        min(p["mon_min"][0] for s in range(1, 21) for p in R["U"][f"U4_{s:02d}"][c]["phases"])))
# ordering persistence in U4
tau4 = []
for s in range(1, 21):
    v = np.array([pagg(R["U"][f"U4_{s:02d}"][c], "g") for c in S5]); tau4.append(kendall(v, base_rank))
print("U4 Kendall tau vs U1 ordering: median %.2f min %.2f" % (np.median(tau4), min(tau4)))

# ------------------------------------------------------------------ jitter distributions
print("=" * 100); print("JITTER: 40 offsets x 3 phases = 120 paths per config")
FAMS = ["J1", "K1", "K2", "K3", "K5ph", "K6ph", "L3a", "L3b", "L4", "L7"]
for fam in FAMS:
    print("-" * 60); print("FAMILY", fam)
    print("%-9s %7s %7s %7s | %6s %6s %6s | %6s %6s | %5s %5s | dlnTW med / P(>S0) | liq tier f1 | minbuf" % ("cfg", "TWmed", "TWp10", "TWp90", "CAGRm", "CAGp10", "CAGp90", "MDDm", "MDDp90", "kilm", "kilp90"))
    base = {(x["off"], x["ph"]): np.log(max(x["tw"], 1e-9)) for x in R["J"][fam]["S0"]}
    for c in ALL:
        rows = R["J"][fam][c]
        tw = np.array([x["tw"] for x in rows]); ca = np.array([x["cagr"] for x in rows]); md = np.array([x["mdd"] for x in rows]); kl = np.array([x["kills"] for x in rows])
        dl = np.array([np.log(max(x["tw"], 1e-9)) - base[(x["off"], x["ph"])] for x in rows])
        nl = sum(x["liq"] for x in rows); n1 = sum(breach(x, 0) for x in rows); nf = sum(breach(x, 4) for x in rows)
        mb = min(x["mon_min"][0] for x in rows)
        print("%-9s %7.2f %7.2f %7.2f | %5.0f%% %5.0f%% %5.0f%% | %5.0f%% %5.0f%% | %5.1f %5.1f | %+6.2f / %.2f | %3d %3d %3d | %6.3f" % (
            LABEL[c], np.median(tw), pct(tw, 10), pct(tw, 90), 100 * np.median(ca), 100 * pct(ca, 10), 100 * pct(ca, 90), 100 * np.median(md), 100 * pct(md, 90),
            np.median(kl), pct(kl, 90), np.median(dl), np.mean(dl > 0), nl, n1, nf, mb))

# ------------------------------------------------------------------ breach matrix & admissibility
print("=" * 100); print("BREACH COUNTS (paths with breach / paths) per stress, by config")
def cnt(fam, c, m):
    rows = R["J"][fam][c]
    return sum(breach(x, m) for x in rows), len(rows)
STRESS = {
    "A1 tier(J1)": lambda c: cnt("J1", c, 0),
    "A2 flat3(J1)": lambda c: cnt("J1", c, 1),
    "A3a gap5(J1)": lambda c: cnt("J1", c, 2),
    "A3 gap10(J1)": lambda c: cnt("J1", c, 3),
    "A4 fund3x(L7)": lambda c: cnt("L7", c, 0),
    "A5 cap10(L3a)": lambda c: cnt("L3a", c, 0),
    "A6a kill-hrWC(K2)": lambda c: cnt("K2", c, 0),
    "A6b kill+1%(K3)": lambda c: cnt("K3", c, 0),
    "A7 delist(U4)": lambda c: (sum(breach(p, 0) for s in range(1, 21) for p in R["U"][f"U4_{s:02d}"][c]["phases"]), 60),
    "A1u tier(U2,U3)": lambda c: (sum(breach(p, 0) for u in keys[1:] for p in R["U"][u][c]["phases"]), 93),
    "A2u flat3(U2,U3)": lambda c: (sum(breach(p, 1) for u in keys[1:] for p in R["U"][u][c]["phases"]), 93),
    "A8 flashF1(J1)": lambda c: cnt("J1", c, 4),
    "X flashF2(J1)": lambda c: cnt("J1", c, 5),
    "P flashF1L(J1)": lambda c: cnt("J1", c, 6),
    "X cap5(L3b)": lambda c: cnt("L3b", c, 0),
}
CORE = ["A1 tier(J1)", "A2 flat3(J1)", "A3 gap10(J1)", "A4 fund3x(L7)", "A5 cap10(L3a)", "A6a kill-hrWC(K2)", "A6b kill+1%(K3)", "A7 delist(U4)", "A1u tier(U2,U3)", "A2u flat3(U2,U3)", "A8 flashF1(J1)"]
EXTREME = ["X flashF2(J1)", "X cap5(L3b)", "A3a gap5(J1)"]
hdr = "%-9s " % "cfg" + " ".join("%-9s" % k.split("(")[0][:9] for k in STRESS)
print(" ".join(["%-9s" % ""] + [k for k in STRESS]))
M = {}
for c in ALL:
    row = {k: f(c) for k, f in STRESS.items()}; M[c] = row
    print("%-9s " % LABEL[c] + " ".join("%d/%d" % row[k] for k in STRESS))
print("\nADMISSIBILITY (core = zero breaches in ALL core stresses)")
adm = {}; adm_nof = {}
for c in ALL:
    bad = [k for k in CORE if M[c][k][0] > 0]
    adm[c] = (len(bad) == 0, bad)
    bad_nof = [k for k in bad if k != "A8 flashF1(J1)"]
    adm_nof[c] = len(bad_nof) == 0
    allbad = bad + [k for k in EXTREME if M[c][k][0] > 0]
    print("%-9s core-admissible=%s  failing core: %s | core-except-F1: %s | ALL(extreme too) failing: %s" % (LABEL[c], adm[c][0], bad, adm_nof[c], allbad))
# min buffers (distance to liquidation) per config, across all J1/U runs
print("\nMIN BUFFER (equity above maintenance, fraction of prior-close equity; 0 = liquidation), min over all J1 paths + U2/U3/U4")
for c in ALL:
    mins = []
    for mi, mn in enumerate(MONN):
        v = [x["mon_min"][mi] for x in R["J"]["J1"][c]]
        v += [p["mon_min"][mi] for u in keys + [f"U4_{s:02d}" for s in range(1, 21)] for p in R["U"][u][c]["phases"]]
        mins.append(min(v))
    print("%-9s " % LABEL[c] + " ".join("%s %7.3f" % (mn, v) for mn, v in zip(MONN, mins)))
print("\nWorst-case family minima (tier MM buffer): K2, K3, L3a, L3b, L7, L4")
for c in ALL:
    print("%-9s " % LABEL[c] + " ".join("%s %6.3f" % (f, min(x["mon_min"][0] for x in R["J"][f][c])) for f in ("K2", "K3", "L3a", "L3b", "L7", "L4")),
          " IM util max (L3a %.2f, L3b %.2f)" % (max(x["imu"] for x in R["J"]["L3a"][c]), max(x["imu"] for x in R["J"]["L3b"][c])))

# ------------------------------------------------------------------ kill-fidelity bootstrap on offset-0 base path
print("=" * 100); print("KILL FIDELITY: base path (offset 0, 3-phase mean) g and bootstrap diff vs S0 per kill model")
for fam in ("J1", "K1", "K2", "K3", "K5ph", "K6ph"):
    r0 = np.mean([rarr(f"{fam}|S0|ph{p}") for p in range(3)], axis=0)
    line = []
    for c in S5:
        rr = np.mean([rarr(f"{fam}|{c}|ph{p}") for p in range(3)], axis=0)
        g = 365 * rr[DS + 1:].mean()
        if c == "S0":
            line.append("%s g %+6.2f" % (LABEL[c], g))
        else:
            b = boot_diff(rr - r0, DS, ND)
            line.append("%s g %+6.2f d %+5.2f [%+5.2f,%+5.2f]" % (LABEL[c], g, b["point"], b["lo_bonf"], b["hi_bonf"]))
    kills = {LABEL[c]: round(float(np.mean([x["kills"] for x in R["J"][fam][c] if x["off"] == 0])), 1) for c in S5}
    print(fam, " | ".join(line), "| kills(off0)", kills)

# ------------------------------------------------------------------ verdicts
print("=" * 100); print("VERDICTS (prereg rule): vs S0 on U1 with Bonferroni CI; persistence over 32 universes; OOS point > 0")
for c in S5[1:]:
    b = BOOT[("U1", c)]
    pf = np.mean(G[c]["full"] > G["S0"]["full"]); pw = np.mean(G[c]["full"] < G["S0"]["full"])
    oos = float(np.mean(G[c]["oos"][:1] - G["S0"]["oos"][:1]))
    if not adm[c][0]:
        v = "inadmissible (liquidation under stress %s)" % ", ".join(adm[c][1])
    elif b["lo_bonf"] > 0 and pf >= 0.7 and oos > 0:
        v = "admissible and better than current"
    elif b["hi_bonf"] < 0 and pw >= 0.7:
        v = "worse"
    else:
        v = "admissible but not distinguishable"
    print("%-8s %s | CI_bonf [%+.3f,%+.3f] persist+ %.2f persist- %.2f OOSdiff %+.3f" % (LABEL[c], v, b["lo_bonf"], b["hi_bonf"], pf, pw, oos))
# also report verdict assuming F1 excluded (sensitivity)
print("\nSensitivity (F1 not binding):")
for c in S5[1:]:
    b = BOOT[("U1", c)]
    pf = np.mean(G[c]["full"] > G["S0"]["full"]); pw = np.mean(G[c]["full"] < G["S0"]["full"]); oos = float(G[c]["oos"][0] - G["S0"]["oos"][0])
    if not adm_nof[c]:
        v = "inadmissible even w/o F1"
    elif b["lo_bonf"] > 0 and pf >= 0.7 and oos > 0:
        v = "admissible and better than current"
    elif b["hi_bonf"] < 0 and pw >= 0.7:
        v = "worse"
    else:
        v = "admissible but not distinguishable"
    print("%-8s %s" % (LABEL[c], v))
print("\nS0 itself: core-admissible=%s failing=%s; w/o F1: %s" % (adm["S0"][0], adm["S0"][1], adm_nof["S0"]))
print("LADDER max zero-breach leverage: core:", max([l for l in LADDER if adm[f"L{l:g}x0.95"][0]] or [None]),
      "| core except F1:", max([l for l in LADDER if adm_nof[f"L{l:g}x0.95"]] or [None]),
      "| ALL incl. extreme:", max([l for l in LADDER if adm[f"L{l:g}x0.95"][0] and all(M[f"L{l:g}x0.95"][k][0] == 0 for k in EXTREME)] or [None]))

# ------------------------------------------------------------------ extra diagnostics
import pandas as pd
days = pd.date_range("2021-06-01", periods=ND, tz="UTC")
print("=" * 100); print("DAY OF MIN TIER BUFFER (J1 offset-0 phase-0 path) and U3 worst subset")
for c in ALL:
    x = [r for r in R["J"]["J1"][c] if r["off"] == 0 and r["ph"] == 0][0]
    worst = min(((p["mon_min"][0], u, p["mon_day"][0]) for u in keys for p in R["U"][u][c]["phases"]))
    print("%-9s J1 minbuf %.3f on %s | worst over U1/U2/U3: %.3f in %s on %s | F1L min %.2f" % (LABEL[c], x["mon_min"][0], days[x["mon_day"][0]].date(), worst[0], worst[1], days[worst[2]].date(), x["mon_min"][6]))
print("\nUNIQUE TRAJECTORIES in jitter (J1): distinct terminal TW among 120 paths")
for c in S5:
    print(LABEL[c], len(set(round(x["tw"], 6) for x in R["J"]["J1"][c])), "of 120")
print("\nflash F1L (post-hoc, long-only 2025-10-10 wick) breach paths in J1 by config:", {LABEL[c]: M[c]["P flashF1L(J1)"][0] for c in ALL})
# S0 U3 detail: how many subsets breach, tier / flat3
for c in ("S0", "S1", "S2", "S3", "S4", "L3.5x0.95"):
    bs = [u for u in keys[2:] if any(breach(p, 0) for p in R["U"][u][c]["phases"])]
    fs = [u for u in keys[2:] if any(breach(p, 1) for p in R["U"][u][c]["phases"])]
    print(LABEL[c], "subsets with tier liquidation:", len(bs), bs, "| flat3 breach:", len(fs))
