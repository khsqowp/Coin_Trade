"""R2-B step 3: stress-day f-factor, minute simultaneity, simultaneous-worst-case ratio.
Inputs: R2B/data/<day>.npz (1m last+mark OHLC, 45 syms), panel npz (books via indep_sim V0 4x/.95/kill.35), prereg.md definitions.
Outputs printed (tee to stress.out) + stress.json."""
import json, os, sys
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__))
R2B = os.path.join(HERE, "..", "docs", "research", "lev_loop", "R2B")
sys.path.insert(0, os.path.join(HERE, "..", "docs", "research", "lev_loop", "review"))
import indep_sim as S
NAMES = S.NAMES
days = json.load(open(os.path.join(R2B, "data", "days.json")))["days"]
THR = 0.01

def hourly(a):
    """a: [N,1440,4] OHLC -> dict arrays [N,24]: prev (ref), lo, hi, close; plus per-minute close [N,24,60]."""
    N = a.shape[0]
    o, h, l, c = (a[:, :, k].reshape(N, 24, 60) for k in range(4))
    prev = np.concatenate([o[:, :1, 0], c[:, :-1, 59]], axis=1)
    return dict(prev=prev, lo=np.nanmin(l, axis=2), hi=np.nanmax(h, axis=2), close=c[:, :, 59], mc=c, ml=l, mh=h)

def stats(x):
    x = np.asarray(x); x = x[np.isfinite(x)]
    if len(x) == 0: return None
    return dict(n=int(len(x)), p10=float(np.quantile(x, .1)), med=float(np.median(x)), p90=float(np.quantile(x, .9)), mean=float(x.mean()))

out = {}
for day in days:
    z = np.load(os.path.join(R2B, "data", day + ".npz"))
    L = hourly(z["last"]); M = hourly(z["mark"])
    cov = np.isfinite(z["last"][:, :, 3]).sum(1) >= 1400
    res = dict(n_cov=int(cov.sum()))
    # ---------- f factor ----------
    fl, fs, pairs_l, pairs_s = [], [], [], []
    wl_l = wl_m = ws_l = ws_m = 0.0
    worst = {}
    for i, n in enumerate(NAMES):
        if not cov[i]: continue
        ll = (L["prev"][i] - L["lo"][i]); lm = (M["prev"][i] - M["lo"][i])
        ul = (L["hi"][i] - L["prev"][i]); um = (M["hi"][i] - M["prev"][i])
        rl = ll / L["prev"][i]; ru = ul / L["prev"][i]
        for h in range(24):
            if rl[h] >= THR and ll[h] > 0:
                fl.append(lm[h] / ll[h]); wl_l += ll[h] / L["prev"][i][h]; wl_m += lm[h] / L["prev"][i][h]
            if ru[h] >= THR and ul[h] > 0:
                fs.append(um[h] / ul[h]); ws_l += ul[h] / L["prev"][i][h]; ws_m += um[h] / L["prev"][i][h]
        hd = int(np.nanargmax(rl)); hu = int(np.nanargmax(ru))
        worst[n] = dict(h_dn=hd, wick_dn=float(rl[hd]), f_dn=float(lm[hd] / ll[hd]) if ll[hd] > 0 else None,
                        h_up=hu, wick_up=float(ru[hu]), f_up=float(um[hu] / ul[hu]) if ul[hu] > 0 else None)
    fdn = [v["f_dn"] for v in worst.values() if v["f_dn"] is not None and v["wick_dn"] >= THR]
    fup = [v["f_up"] for v in worst.values() if v["f_up"] is not None and v["wick_up"] >= THR]
    res["f_hours_dn"] = stats(fl); res["f_hours_up"] = stats(fs)
    res["f_pooled_dn"] = wl_m / wl_l if wl_l > 0 else None; res["f_pooled_up"] = ws_m / ws_l if ws_l > 0 else None
    res["f_worst_hour_dn"] = stats(fdn); res["f_worst_hour_up"] = stats(fup)
    res["frac_f_dn_ge_0.97"] = float(np.mean(np.array(fdn) >= 0.97)) if fdn else None
    res["frac_f_dn_ge_1.0"] = float(np.mean(np.array(fdn) >= 1.0)) if fdn else None
    res["n_sig_dn_symbols"] = len(fdn); res["n_sig_up_symbols"] = len(fup)
    res["worst"] = worst
    # ---------- books ----------
    D = int(S.DAYS.searchsorted(pd.Timestamp(day, tz="UTC")))
    books = {}
    for ph in range(3):
        r = S.run(phase=ph, record=True); src = "V0-kill.35"
        if D not in r["rec"]:      # V0 book was flat (killed/cooldown) that day -> same engine WITHOUT kill (kill=9) to get a live-like book
            r = S.run(phase=ph, record=True, kill=9.0); src = "V0-nokill"
        if D not in r["rec"]:      # flat because of the BTC crash filter -> hypothetical book WITHOUT crash filter and kill (labelled)
            _c = S.CRASH.copy(); S.CRASH[:] = False
            r = S.run(phase=ph, record=True, kill=9.0); src = "HYP-nocrashfilter"; S.CRASH[:] = _c
        if D in r["rec"]:
            q, e, W = r["rec"][D]; books[ph] = (q.copy(), e.copy(), W, float(r["eq"][D - 1]) if np.isfinite(r["eq"][D - 1]) else np.nan)
    res["books"] = {}
    for ph, (q, e, W, peq) in books.items():
        held = q != 0
        gross = np.abs(q) * np.where(np.isfinite(S.C[D, 0]), S.C[D, 0], e)
        gross = np.where(held, gross, 0.0)
        have = cov & held
        covg = float(gross[have].sum() / gross.sum()) if gross.sum() > 0 else np.nan
        qq = np.where(have, q, 0.0)
        bk = dict(src=src, n_held=int(held.sum()), n_have=int(have.sum()), gross_cov=covg, gross_over_eq=float(gross.sum() / peq) if peq == peq else None)
        longs = qq > 0; shorts = qq < 0
        for tag, P in (("last", L), ("mark", M)):
            c = np.nan_to_num(P["close"]); Eclose = W + np.nansum(qq[:, None] * (np.nan_to_num(P["close"]) - e[:, None]), axis=0)  # [24]
            # hour close equity (only covered syms differ slightly from panel; use equity base from covered book)
            anti_x = np.where(qq[:, None] > 0, P["lo"], P["hi"])
            anti_loss = np.nansum(qq[:, None] * (c - np.nan_to_num(anti_x)), axis=0)               # Eclose - Eanti  (>=0)
            mc = np.nan_to_num(P["mc"])                                                             # [N,24,60] minute closes
            inst_close = np.nansum(qq[:, None, None] * (c[:, :, None] - mc), axis=0)               # [24,60] Eclose - Einst(m)
            inst_loss = inst_close.max(axis=1)
            ml = np.where(qq[:, None, None] > 0, np.nan_to_num(P["ml"]), np.nan_to_num(P["mh"]))   # minute anti-sync
            inst_lh = np.nansum(qq[:, None, None] * (c[:, :, None] - ml), axis=0).max(axis=1)
            base = np.maximum(Eclose, 1e-9)
            a = anti_loss / base; i1 = inst_loss / base; i2 = inst_lh / base
            hw = int(np.argmax(a))
            # loss vs PREVIOUS hour close variant (worst minute vs hourly simultaneous L/H)
            prev = np.nan_to_num(P["prev"])
            pa = np.nansum(qq[:, None] * (np.nan_to_num(anti_x) - prev), axis=0)                    # <=0 typically
            pm = np.nansum(qq[:, None, None] * (mc - prev[:, :, None]), axis=0).min(axis=1)
            bk[tag] = dict(worst_hour=hw, anti_worst_hour=float(a[hw]), inst1m_close_worst_hour=float(i1[hw]), inst1m_LH_worst_hour=float(i2[hw]),
                           ratio_close_worst_hour=float(i1[hw] / a[hw]) if a[hw] > 0 else None,
                           ratio_LH_worst_hour=float(i2[hw] / a[hw]) if a[hw] > 0 else None,
                           ratio_close_pooled=float(i1.sum() / a.sum()) if a.sum() > 0 else None,
                           ratio_close_median_hours=float(np.median(i1[a > 0.002] / a[a > 0.002])) if (a > 0.002).any() else None,
                           prevclose_ratio_worst_hour=float(pm[hw] / pa[hw]) if pa[hw] < 0 else None,
                           anti_loss_over_close_max=float(a.max()), anti_median_hours=float(np.median(a)))
            # ---------- simultaneity within worst hour ----------
            ix = np.where(have)[0]; lo_m = np.full(len(NAMES), -1); hi_m = np.full(len(NAMES), -1)
            lo_m[ix] = np.nanargmin(P["ml"][ix][:, hw, :], axis=1); hi_m[ix] = np.nanargmax(P["mh"][ix][:, hw, :], axis=1)
            Lm = lo_m[longs & have]; Sm = hi_m[shorts & have]
            if len(Lm) and len(Sm):
                dif = np.abs(Lm[:, None] - Sm[None, :])
                bk[tag]["sim"] = dict(n_long=len(Lm), n_short=len(Sm), iqr_long_low_min=float(np.subtract(*np.percentile(Lm, [75, 25]))),
                                      iqr_short_high_min=float(np.subtract(*np.percentile(Sm, [75, 25]))),
                                      frac_pairs_within5=float((dif <= 5).mean()), med_long_low_min=float(np.median(Lm)), med_short_high_min=float(np.median(Sm)))
            # basket pnl correlation over the day (1m)
            flat = lambda m: np.nan_to_num(P["mc"]).reshape(len(NAMES), 1440)
            mcf = flat(0)
            pl = (qq * longs)[:, None] * mcf; ps = (qq * shorts)[:, None] * mcf
            dl = np.diff(pl.sum(0)); ds = np.diff(ps.sum(0))
            bk[tag]["corr_LS_day"] = float(np.corrcoef(dl, ds)[0, 1])
            sl = slice(hw * 60, hw * 60 + 60)
            bk[tag]["corr_LS_worst_hour"] = float(np.corrcoef(dl[sl.start:sl.stop - 1], ds[sl.start:sl.stop - 1])[0, 1])
            bk[tag]["worst_hour_pnl_L"] = float((pl.sum(0)[sl.stop - 1] - pl.sum(0)[sl.start]) / peq)
            bk[tag]["worst_hour_pnl_S"] = float((ps.sum(0)[sl.stop - 1] - ps.sum(0)[sl.start]) / peq)
        res["books"][ph] = bk
    out[day] = res
json.dump(out, open(os.path.join(R2B, "stress.json"), "w"), indent=1, default=float)
# ---------- printing ----------
def fm(x, p=2): return "NA" if x is None else f"{x:.{p}f}"
print("== f-factor (mark wick / last wick), wick >= 1% ==")
print("day | cov | sig-sym dn | f_worstHour dn p10/med/p90 | frac f>=0.97 | f_hours dn p10/med/p90 (n) | pooled dn | up: sig | f_worstHour up p10/med/p90 | pooled up")
for d, r in out.items():
    a = r["f_worst_hour_dn"]; b = r["f_hours_dn"]; c = r["f_worst_hour_up"]
    print(d, "|", r["n_cov"], "|", r["n_sig_dn_symbols"], "|", (f"{a['p10']:.2f}/{a['med']:.2f}/{a['p90']:.2f}" if a else "NA"), "|", fm(r["frac_f_dn_ge_0.97"]), "|",
          (f"{b['p10']:.2f}/{b['med']:.2f}/{b['p90']:.2f} ({b['n']})" if b else "NA"), "|", fm(r["f_pooled_dn"]), "|", r["n_sig_up_symbols"], "|",
          (f"{c['p10']:.2f}/{c['med']:.2f}/{c['p90']:.2f}" if c else "NA"), "|", fm(r["f_pooled_up"]))
print("\n== simultaneity / simultaneous-worst-case ratio (V0 4x books, per phase) ==")
print("day ph | gross/eq cov | tag | worst-h | anti%(close-basis) | inst1m(close)% | inst1m(L/H)% | ratio close | ratio L/H | pooled ratio | med-h ratio | prevclose-ratio | corrLS day/hour | withinÂ±5 pairs | IQR Llow/Shigh | pnlL/pnlS(worst h, %eq)")
for d, r in out.items():
    for ph, bk in r["books"].items():
        for tag in ("last", "mark"):
            t = bk[tag]; s = t.get("sim", {})
            print(d, ph, bk["src"], "|", fm(bk["gross_over_eq"]), fm(bk["gross_cov"]), "|", tag, "|", t["worst_hour"], "|", fm(100 * t["anti_worst_hour"]), "|", fm(100 * t["inst1m_close_worst_hour"]), "|", fm(100 * t["inst1m_LH_worst_hour"]), "|",
                  fm(t["ratio_close_worst_hour"]), "|", fm(t["ratio_LH_worst_hour"]), "|", fm(t["ratio_close_pooled"]), "|", fm(t["ratio_close_median_hours"]), "|", fm(t["prevclose_ratio_worst_hour"]), "|",
                  fm(t["corr_LS_day"]), "/", fm(t["corr_LS_worst_hour"]), "|", fm(s.get("frac_pairs_within5")), "|", fm(s.get("iqr_long_low_min"), 0), "/", fm(s.get("iqr_short_high_min"), 0), "|",
                  fm(100 * t["worst_hour_pnl_L"], 1), "/", fm(100 * t["worst_hour_pnl_S"], 1))
