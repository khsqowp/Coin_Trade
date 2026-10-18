"""Cross-check rs_final_engine vs rs_risk_engine.simulate (same data, 14/3/8, 1x) + survivorship ablation."""
import numpy as np, pandas as pd, time
from app.rs_final_data import load_panel, universe
from app.rs_final_engine import Sim, window_metrics
from app.rs_risk_load import load
from app.rs_risk_engine import build_panel, simulate, Cfg


def main():
    ohlc, fund = load()
    uni = universe()
    ohlc = {b: ohlc[b] for b in uni if b in ohlc}; fund = {b: fund[b] for b in uni if b in fund}
    P2 = build_panel(ohlc, fund)
    S = Sim(load_panel())
    for lev, K, reb in ((1.0, 8, 3), (1.0, 12, 2)):
        m = simulate(P2, Cfg(lookback=14, rebal=reb, K=K, lev=lev))
        r = S.run(lbs=(14,), rebal=reb, K=K, lev=lev, d0=0, phase=0)
        mm = window_metrics(r)
        print(f"K{K} R{reb}: risk_engine final {m['final']:.3f} cagr {m['cagr']*100:.1f}% imdd {m['imdd']*100:.1f}% | final_engine final {mm['end']:.3f} cagr {mm['cagr']*100:.1f}% imdd {mm['imdd']*100:.1f}%")
    # ablation: drop coins listed after 2023-01-01 (recent-listing / survivorship-heavy names)
    c = S.C[:, -1, :]; first = np.argmax(np.isfinite(c), axis=0)
    late = [n for j, n in enumerate(S.names) if S.days[first[j]] >= pd.Timestamp("2023-01-01", tz="UTC")]
    print("late-listed dropped:", late)
    keep = [j for j, n in enumerate(S.names) if n not in late]
    Pk = dict(names=[S.names[j] for j in keep], days=S.days, H=S.H[:, :, keep], L=S.L[:, :, keep], C=S.C[:, :, keep], FD=S.FD[:, keep])
    Sk = Sim(Pk)
    for nm, SS in (("all45", S), (f"ex-late({len(keep)})", Sk)):
        for cw in (0, 1):
            ms = [window_metrics(SS.run(lbs=(14,), rebal=3, K=8, cw=cw, phase=p)) for p in range(3)]
            print(nm, "const-weight" if cw else "qty-keeping", f"CAGR {np.mean([m['cagr'] for m in ms])*100:.1f}% imdd {np.mean([m['imdd'] for m in ms])*100:.1f}% Calmar {np.mean([m['calmar'] for m in ms]):.2f}")
        # by-regime: IS/OOS
        for cw in (0, 1):
            for a, b in (("2022-01-01", "2024-06-30"), ("2024-07-01", None)):
                ms = [window_metrics(SS.run(lbs=(14,), rebal=3, K=8, cw=cw, phase=p), a, b) for p in range(3)]
                print("   ", "cw" if cw else "qk", a[:7], f"CAGR {np.mean([m['cagr'] for m in ms])*100:.1f}% imdd {np.mean([m['imdd'] for m in ms])*100:.1f}%")

main()
