"""Future-perturbation (no look-ahead) test for every re-implemented family: replace ALL data after day t0 with garbage, recompute,
and require rows <= t0 of pos and strength to be identical. Uses 3 random cut dates x (first grid point + a random grid point) x tfs."""
from __future__ import annotations
import copy, json, sys, time
import numpy as np
from app.rs_map_off_data import load_data
from app.rs_map_off_run import registry, grid_points


def perturbed(D, t0, rng):
    D2 = dict(D)
    d = {k: v.copy() for k, v in D["d"].items()}; b = {k: v.copy() for k, v in D["b4"].items()}
    for k in d:
        sh = d[k][t0 + 1:].shape
        d[k][t0 + 1:] = d[k][t0 + 1:] * rng.lognormal(0, 0.5, sh) + rng.normal(0, 1e-3, sh) * np.nanmean(np.abs(d[k]))
    for k in b:
        sh = b[k][(t0 + 1) * 6:].shape
        b[k][(t0 + 1) * 6:] = b[k][(t0 + 1) * 6:] * rng.lognormal(0, 0.5, sh)
    # keep OHLC internally sane-ish is NOT required: a causal rule must ignore them entirely
    D2["d"], D2["b4"] = d, b
    return D2


def check(fam, D, tf, p, t0s, rng):
    pos, st = fam["fn"](D, tf, **p)
    bad = []
    for t0 in t0s:
        D2 = perturbed(D, t0, rng)
        pos2, st2 = fam["fn"](D2, tf, **p)
        for nm, a, b in (("pos", pos, pos2), ("strength", st, st2)):
            x = np.asarray(a, float)[: t0 + 1]; y = np.asarray(b, float)[: t0 + 1]
            same = (np.isnan(x) == np.isnan(y)) & (np.isnan(x) | np.isclose(x, y, rtol=1e-9, atol=1e-12))
            if not same.all():
                bad.append((nm, t0, int((~same).sum())))
    return bad


def main():
    D = load_data(); reg = registry(); rng = np.random.RandomState(5)
    nd = len(D["days"])
    out = {}
    for name, fam in reg.items():
        pts = list(grid_points(fam))
        chosen = [pts[0], pts[len(pts) // 2], pts[-1]]
        res = []
        for tf in fam["tfs"]:
            for p in chosen:
                t0s = [int(x) for x in rng.randint(400, nd - 40, 3)]
                t = time.time()
                try:
                    bad = check(fam, D, tf, p, t0s, rng)
                except Exception as e:  # noqa
                    bad = [("ERROR", repr(e)[:80], 0)]
                res.append((tf, p, bad))
        ok = all(not b for _, _, b in res)
        out[name] = dict(ok=ok, bad=[(tf, p, b) for tf, p, b in res if b][:2])
        print(f"{name:40s} {'PASS' if ok else 'FAIL'}", "" if ok else str(out[name]["bad"])[:200], flush=True)
    json.dump(out, open("/private/tmp/claude-501/-Users-user-Desktop-CODE-Ochestration/20fd8e9e-6d26-4ff1-a6b5-39a3bd8d3e48/scratchpad/mapoff/perturb.json", "w"), default=str)


if __name__ == "__main__":
    main()
