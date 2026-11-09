"""BACKTESTER-B: run the pre-registered grid (docs/research/tp_loop/B/prereg.md). Writes a pickle to RS_FINAL_SCRATCH."""
import os, pickle, time
import numpy as np
from app.rs_final_data import load_panel
from app.rs_tp_b_engine import TPSim, tp_params

# id: (mode, kA, kB, vol)
GRID = {
    "T_atr2": (1, 2.0, 0.0, "atr"), "T_atr3": (1, 3.0, 0.0, "atr"), "T_atr5": (1, 5.0, 0.0, "atr"), "T_atr8": (1, 8.0, 0.0, "atr"),
    "T_rv3": (1, 3.0, 0.0, "rv"),
    "R_4_2": (2, 4.0, 2.0, "atr"), "R_6_2": (2, 6.0, 2.0, "atr"), "R_6_3": (2, 6.0, 3.0, "atr"), "R_8_3": (2, 8.0, 3.0, "atr"),
    "S_4": (3, 4.0, 0.0, "atr"), "S_6": (3, 6.0, 0.0, "atr"), "S_8": (3, 8.0, 0.0, "atr"),
}
# scenario: (lev, deploy, redeploy, nextbar, cost, slip, fund_mult, fund_extra)
SCEN = {
    "main": (4.0, 0.95, 0, 0, 0.001, 0.0005, 1.0, 0.0),
    "redeploy": (4.0, 0.95, 1, 0, 0.001, 0.0005, 1.0, 0.0),
    "cost2x": (4.0, 0.95, 0, 0, 0.002, 0.0010, 1.0, 0.0),
    "nextbar": (4.0, 0.95, 0, 1, 0.001, 0.0005, 1.0, 0.0),
    "fundstress": (4.0, 0.95, 0, 0, 0.001, 0.0005, 3.0, 1e-4),
    "lev2": (2.0, 1.0, 0, 0, 0.001, 0.0005, 1.0, 0.0),
    "lev2_redeploy": (2.0, 1.0, 1, 0, 0.001, 0.0005, 1.0, 0.0),
}


def one(S, cfg, sc, kA=None, kB=None):
    lev, dep, red, nb, cost, slip, fm, fx = SCEN[sc]
    out = []
    for ph in range(3):
        if cfg == "V0":
            tp = tp_params(0, 0, 0, red, nb, slip, fm, fx); vol = "atr"
        else:
            m, a, b, vol = GRID[cfg]
            tp = tp_params(m, a if kA is None else kA, b if kB is None else kB, red, nb, slip, fm, fx)
        r = S.run_tp(tp, lev=lev, deploy=dep, cost=cost, phase=ph, vol=vol)
        eq = r["eq"].to_numpy()[r["d0"]:]
        eq = np.nan_to_num(eq, nan=0.0)
        prev = np.r_[1.0, eq[:-1]]
        ret = np.where(prev > 0, eq / np.where(prev > 0, prev, 1) - 1, 0.0)
        out.append(dict(ret=ret, expo=r["expo"].to_numpy()[r["d0"]:], stats=r["stats"], trades=r["trades"], events=r["events"],
                        worst=r["worst"].to_numpy()[r["d0"]:]))
    return out


def main():
    S = TPSim(load_panel())
    res = {"days": S.days[S.d_start():], "names": S.names}
    t0 = time.time()
    for sc in SCEN:
        res[(sc, "V0")] = one(S, "V0", sc)
        for c in GRID:
            res[(sc, c)] = one(S, c, sc)
        print(sc, "done", round(time.time() - t0, 1), flush=True)
    # +-25% neighbours (main scenario), every parameter
    for c, (m, a, b, vol) in GRID.items():
        for fa in (0.75, 1.25):
            res[("nbr", c, "A", fa)] = one(S, c, "main", kA=a * fa)
        if m == 2:
            for fb in (0.75, 1.25):
                res[("nbr", c, "B", fb)] = one(S, c, "main", kB=b * fb)
    print("neighbours done", round(time.time() - t0, 1))
    # panel pieces for diagnostics
    res["C_close"] = S.C[S.d_start():, -1, :]
    res["atr"] = S.atr[S.d_start():]
    res["rv"] = S.rv[S.d_start():]
    pickle.dump(res, open(os.path.join(os.environ["RS_FINAL_SCRATCH"], "tp_b_res.pkl"), "wb"))


if __name__ == "__main__":
    main()
