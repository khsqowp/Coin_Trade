"""R2-B step 5: reconstruct LIVE equity from state (entry_log snapshots) + public 1m mark prices; calibrate vs live equity_history; empirical lambda.
Read-only on a COPY of the state (state_fresh.json taken via docker exec read-only). usage: python rs_lev_r2b_live.py <state.json> <live_dir>"""
import json, os, sys, bisect
import numpy as np, pandas as pd
st_path, live_dir = sys.argv[1], sys.argv[2]
OUT = "/Users/user/Desktop/CODE/Ochestration/trading/docs/research/lev_loop/review2/rerun/_out_r2b_live"
s = json.load(open(st_path))
T0 = int(pd.Timestamp("2026-09-24", tz="UTC").timestamp() * 1000)
syms = sorted(set(e["symbol"] for e in s["entry_log"]))
MK = {x: np.load(os.path.join(live_dir, f"mark1m_{x}.npy")).astype(np.float64) for x in syms}
T = min(len(v) for v in MK.values()); MK = {x: v[:T] for x, v in MK.items()}
def ms(ts): return pd.Timestamp(ts).value // 10**6
def px(x, t_ms):
    a = MK[x]; m = (t_ms - T0) // 60000; fr = ((t_ms - T0) % 60000) / 60000.0
    if m < 0 or m >= T or not np.isfinite(a[m, 3]): return np.nan
    return a[m, 0] + (a[m, 3] - a[m, 0]) * fr
# ---- snapshots
snaps = {}
for e in s["entry_log"]:
    snaps.setdefault(e["ts"], []).append(e)
snap_ts = sorted(snaps, key=ms)
seg = []   # (start_ms, end_ms, {sym: signed qty})
for k, ts in enumerate(snap_ts):
    t = ms(ts); q = {}
    for e in snaps[ts]:
        p = px(e["symbol"], t)
        if np.isfinite(p) and p > 0: q[e["symbol"]] = (1 if e["side"] == "long" else -1) * e["notional_usdt"] / p
    seg.append([t, ms(snap_ts[k + 1]) if k + 1 < len(snap_ts) else 10**15, q])
# flat windows (from trade_log): manual flatten -> next rebalance complete, kill -> next rebalance complete
tl = s["trade_log"]
flat_win = []
def first_ts(pref, after):
    for e in tl:
        if e["message"].startswith(pref) and e["ts"] >= after: return ms(e["ts"])
flat_win.append((ms("2026-10-11T09:09:18.279Z"), ms("2026-10-11T09:12:58.268Z")))
flat_win.append((ms("2026-10-12T05:50:11.100Z"), ms("2026-10-14T09:14:27.632Z")))
def is_flat(t): return any(a <= t < b for a, b in flat_win)
# ---- current positions check (last snapshot vs state positions)
chk = {}
for b, p in s["positions"].items():
    q_state = (1 if p["side"] == "long" else -1) * p["notional_usdt"] / p["mark_price"]
    q_snap = seg[-1][2].get(b)
    chk[b] = (q_state, q_snap, (q_snap / q_state - 1) if q_snap else None)
dev = [abs(v[2]) for v in chk.values() if v[2] is not None]
print("last-snapshot qty vs state positions: n", len(chk), "max |dev| %.2f%%  median %.2f%%" % (100 * max(dev), 100 * np.median(dev)),
      "missing", [b for b, v in chk.items() if v[1] is None])
# ---- equity series
eh = s["equity_history"]
t_l = np.array([ms(x["ts"]) for x in eh]); E_l = np.array([x["equity_usdt"] for x in eh])
keep = (t_l >= T0 + 24 * 3600 * 1000) & (t_l < T0 + (T - 5) * 60000)
t_l, E_l = t_l[keep], E_l[keep]
def pos_at(t):
    for a, b, q in seg:
        if a <= t < b: return q
    return {}
def pnl_vec(q, t_ms_arr):
    """sum q_i * P_i(t) for array of ms times (vectorised per symbol, 1m-interp)"""
    tot = np.zeros(len(t_ms_arr))
    m = (t_ms_arr - T0) // 60000; fr = ((t_ms_arr - T0) % 60000) / 60000.0
    for x, qq in q.items():
        a = MK[x]; p = a[m, 0] + (a[m, 3] - a[m, 0]) * fr
        tot += qq * p
    return tot
# ---- per-segment residuals
rows = []   # (seg_idx, t, E_live, Erec_delta)
for k, (a, b, q) in enumerate(seg):
    idx = np.where((t_l >= a) & (t_l < b))[0]
    if len(idx) < 3: continue
    # split around flat windows
    fl = np.array([is_flat(int(t)) for t in t_l[idx]])
    for tag in (False, True):
        sel = idx[fl == tag]
        if len(sel) < 3: continue
        Er = np.zeros(len(sel)) if tag else pnl_vec(q, t_l[sel])
        rows.append((k, tag, t_l[sel], E_l[sel], Er))
res_all, base_all, res_anch, dres5 = [], [], [], []
n_live_nonflat = int(sum(len(r[2]) for r in rows if not r[1]))
n_total = len(t_l)
seg_stats = []
for k, tag, t, El, Er in rows:
    if tag: continue
    d_live = El - El[0]; d_rec = Er - Er[0]
    r = d_rec - d_live
    off = np.median(r)
    rr = (r - off) / El
    res_all.append(rr); res_anch.append(r / El)
    dres5.append(np.diff(r) / El[1:])
    seg_stats.append((k, pd.Timestamp(t[0], unit="ms", tz="UTC"), len(t), float(np.sqrt(np.mean(rr ** 2))), float(np.sqrt(np.mean((r / El) ** 2))), float(off / El.mean())))
R = np.concatenate(res_all); RA = np.concatenate(res_anch); D5 = np.concatenate(dres5)
rmse = float(np.sqrt(np.mean(R ** 2))); rmse_a = float(np.sqrt(np.mean(RA ** 2))); rmse5 = float(np.sqrt(np.mean(D5 ** 2)))
live5 = np.concatenate([np.diff(r[3]) / r[3][1:] for r in rows if not r[1]])
cover = n_live_nonflat / max(1, n_total - sum(len(r[2]) for r in rows if r[1]))
print(f"live samples total {n_total}, in flat windows {sum(len(r[2]) for r in rows if r[1])}, reconstructed non-flat {n_live_nonflat} (coverage of non-flat {cover:.1%})")
print(f"PRIMARY level RMSE (segment-median removed): {100*rmse:.3f}% of equity | anchored-at-start RMSE {100*rmse_a:.3f}% | 5-min increment RMSE {100*rmse5:.3f}% (live 5-min increment std {100*np.std(live5):.3f}%)")
print("segment table: start | n | rmse(demeaned) % | rmse(anchored) % | offset/E %")
for k, t0_, n, a, b, c in seg_stats: print(k, str(t0_)[:19], n, f"{100*a:.3f}", f"{100*b:.3f}", f"{100*c:.2f}")
os.makedirs(OUT, exist_ok=True)
json.dump(dict(rmse=rmse, rmse_anchored=rmse_a, rmse_5min_incr=rmse5, live_5min_std=float(np.std(live5)), coverage=cover, qty_dev_max=max(dev), qty_dev_median=float(np.median(dev)),
               segs=[(int(k), str(t), int(n), a, b, c) for k, t, n, a, b, c in seg_stats]), open(os.path.join(OUT, "live_calib.json"), "w"), indent=1)
# ================= lambda stage (always computed; labelled CALIBRATED / NOT by RMSE rule) =================
ok = (rmse <= 0.003) and (cover >= 0.70) and (max(dev) <= 0.03)
print("CALIBRATION VERDICT:", "PASS" if ok else "FAIL", f"(rmse {100*rmse:.3f}% <=0.30%? {rmse<=0.003}; coverage>=70%? {cover>=0.70}; qty dev<=3%? {max(dev)<=0.03})")
hours = []   # dict rows
Emin_series = []  # (ms, E_level)
for k, tag, t, El, Er in rows:
    if tag: continue
    a_, b_, q = seg[k]
    m_first = int((t[0] - T0) // 60000); m_last = int((t[-1] - T0) // 60000)
    ms_idx = np.arange(m_first, m_last + 1)
    tms = T0 + ms_idx * 60000 + 59999    # minute close time
    Rabs_close = np.zeros(len(ms_idx)); 
    for x, qq in q.items(): Rabs_close += qq * MK[x][ms_idx, 3]
    # level offset from samples: use absolute Erec at sample times
    Erec_abs_samples = pnl_vec(q, t)
    c = float(np.median(El - Erec_abs_samples))
    Elev = Rabs_close + c
    for mi, e_ in zip(ms_idx, Elev): Emin_series.append((T0 + int(mi) * 60000, e_))
    h0 = int(np.ceil(m_first / 60)); h1 = int(np.floor((m_last + 1) / 60)) - 1
    for h in range(h0, h1 + 1):
        sl = np.arange(h * 60, h * 60 + 60)
        Ec = Elev[sl - m_first]
        eclose = Ec[-1]; dip_close = (eclose - Ec.min()) / eclose
        anti = 0.0; lh_min = 0.0
        # anti-sync hourly worst: longs at hourly low, shorts at hourly high (mark 1m)
        for x, qq in q.items():
            a_x = MK[x][sl]
            Cc = a_x[-1, 3]
            X = a_x[:, 2].min() if qq > 0 else a_x[:, 1].max()
            anti += qq * (Cc - X)
        anti /= eclose
        # minute anti-sync (each minute: longs at minute low, shorts at minute high) relative to hour close
        mlh = np.zeros(60)
        for x, qq in q.items():
            a_x = MK[x][sl]
            mlh += qq * (a_x[-1, 3] - (a_x[:, 2] if qq > 0 else a_x[:, 1]))
        dip_lh = mlh.max() / eclose
        gross = sum(abs(qq) * MK[x][sl[-1], 3] for x, qq in q.items()) / eclose
        hours.append((int(T0 + h * 3600000), float(dip_close), float(dip_lh), float(anti), float(gross), float(eclose)))
H = np.array(hours)
dip, dlh, anti, gross = H[:, 1], H[:, 2], H[:, 3], H[:, 4]
m = anti > 0
print(f"hours {len(H)}; mean gross/eq {gross.mean():.2f}")
print("1m-close dip below hour close:   mean %.4f p50 %.4f p90 %.4f p99 %.4f max %.4f" % (dip.mean(), np.median(dip), np.quantile(dip, .9), np.quantile(dip, .99), dip.max()))
print("1m anti-sync(min L/H) dip:       mean %.4f p50 %.4f p90 %.4f p99 %.4f max %.4f" % (dlh.mean(), np.median(dlh), np.quantile(dlh, .9), np.quantile(dlh, .99), dlh.max()))
print("hourly anti-sync L/H worst:      mean %.4f p50 %.4f p90 %.4f p99 %.4f max %.4f" % (anti.mean(), np.median(anti), np.quantile(anti, .9), np.quantile(anti, .99), anti.max()))
lam_pool = dip.sum() / anti.sum(); lam_lh = dlh.sum() / anti.sum()
lam_h = dip[m] / anti[m]
print(f"lambda(pooled, 1m closes) {lam_pool:.3f} | lambda(pooled, 1m L/H) {lam_lh:.3f} | per-hour lambda p10/p50/p90 {np.quantile(lam_h,.1):.3f}/{np.median(lam_h):.3f}/{np.quantile(lam_h,.9):.3f}")
# block bootstrap CI over days for pooled lambda
day = ((H[:, 0] - T0) // 86400000).astype(int)
ud = np.unique(day); rng = np.random.default_rng(20261031); bs = []
for _ in range(2000):
    pick = rng.choice(ud, len(ud)); i1 = np.concatenate([np.where(day == d)[0] for d in pick]); bs.append(dip[i1].sum() / anti[i1].sum())
print("pooled lambda block-bootstrap(days) 90%% CI %.3f..%.3f" % (np.quantile(bs, .05), np.quantile(bs, .95)))
# 15-second correction note: review measured x1.21 for 15s vs 5-min subsample; apply to dip for bracket
print("lambda x1.21 (15s-vs-5min factor from review) pooled %.3f" % (1.21 * lam_pool))
# ---- DD trigger comparison: 1m vs hourly-close vs daily-close (same raw hwm convention, live period)
M = np.array(Emin_series); M = M[np.argsort(M[:, 0])]
tm, Em = M[:, 0], M[:, 1]
def dd_series(t, e):
    hw = np.maximum.accumulate(e); return 1 - e / hw
hh = (tm - T0) // 3600000
last_idx = np.where(np.r_[hh[1:] != hh[:-1], True])[0]
dd_1m = dd_series(tm, Em); dd_h = dd_series(tm[last_idx], Em[last_idx])
dd_idx = (tm[last_idx] - T0) // 86400000
dl = np.where(np.r_[dd_idx[1:] != dd_idx[:-1], True])[0]
dd_d = dd_series(tm[last_idx][dl], Em[last_idx][dl])
print("MaxDD  1m %.4f | hourly-close %.4f | daily-close %.4f   (non-flat minutes only)" % (dd_1m.max(), dd_h.max(), dd_d.max()))
def episodes(dd, th, hyst=0.02):
    n = 0; armed = True
    for x in dd:
        if armed and x >= th: n += 1; armed = False
        elif (not armed) and x < th - hyst: armed = True
    return n
print("threshold | episodes 1m | hourly-close | daily-close | minutes with DD>=th (1m)")
for th in (0.10, 0.15, 0.20, 0.25, 0.27, 0.30, 0.35):
    print(f"{th:.2f} | {episodes(dd_1m, th)} | {episodes(dd_h, th)} | {episodes(dd_d, th)} | {int((dd_1m >= th).sum())}")
json.dump(dict(calibrated=bool(ok), lam_pool=float(lam_pool), lam_lh=float(lam_lh), lam_h_p10_50_90=[float(np.quantile(lam_h, q)) for q in (.1, .5, .9)],
               boot90=[float(np.quantile(bs, .05)), float(np.quantile(bs, .95))], n_hours=int(len(H)),
               dip=dict(mean=float(dip.mean()), p50=float(np.median(dip)), p90=float(np.quantile(dip, .9)), p99=float(np.quantile(dip, .99)), mx=float(dip.max())),
               anti=dict(mean=float(anti.mean()), p50=float(np.median(anti)), p90=float(np.quantile(anti, .9)), p99=float(np.quantile(anti, .99)), mx=float(anti.max())),
               maxdd=dict(m1=float(dd_1m.max()), hour=float(dd_h.max()), day=float(dd_d.max()))), open(os.path.join(OUT, "live_lambda.json"), "w"), indent=1)
