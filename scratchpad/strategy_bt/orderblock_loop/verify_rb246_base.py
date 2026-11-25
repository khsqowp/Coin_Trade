import sys, time, json, pickle
sys.path.insert(0, "/Users/user/CODE/Coin_Trade/scratchpad/strategy_bt/orderblock_loop")
import verify_rb246_independent as V
t=time.time()
syms = V.load_universe()
P = V.load_panel(syms)
funds = [V.load_funding(s) for s in syms]
D = V.day_count(P)
print("T", P["T"], "S", len(syms), "misaligned", P["misaligned"], "D", D, "load s", round(time.time()-t,1))
print("funding missing:", [s for s,f in zip(syms,funds) if f is None])
cfgs = V.f4_grid()
res = {}
for c in cfgs:
    tr, info = V.run(P, c, funds)
    m = V.metrics(tr, P["t0"], D)
    m.update(info)
    res[c["label"]] = {"cfg": c, "m": m}
    print(c["label"], c["top_k"], c["rs"], c["reg"], "n", m["n"], "PF", round(m["PF"],3), "exp", round(m["exp_bp"],1),
          "cum", round(m["cum"],3), "p", f'{m["p_one"]:.2e}', "core", m["core_pass"], "bonf", m["bonf_pass"], "cens", info["censored"], flush=True)
json.dump(res, open("/private/tmp/claude-501/-Users-user-CODE-Ochestration/ee6baff2-9664-4b9e-9a9e-5f263219aa7c/scratchpad/rb246_out/f4_grid.json","w"), indent=1, default=float)
print("elapsed", round(time.time()-t,1))
