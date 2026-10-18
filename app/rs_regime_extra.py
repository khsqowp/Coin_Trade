"""Controls + robustness for the best regime designs (research only)."""
from __future__ import annotations
import numpy as np, pandas as pd
from app.rs_regime_lib import Engine, Config, load_cache, metrics

c, f, _ = load_cache()
E = Engine(c, f); E.prepare()
SPL = {"TRAIN": ("2022-01-01", "2024-06-30"), "OOS": ("2024-07-01", "2030-01-01"), "FULL": ("2022-01-01", "2030-01-01")}

def m(daily, a, b):
    d = daily.loc[a:b]
    mm = metrics(d)
    return mm

def row(name, res):
    d = res["daily"]; out = [name]
    for k, (a, b) in SPL.items():
        mm = m(d, a, b); out += [f"{mm['CAGR']*100:5.1f}", f"{mm['MDD']*100:5.1f}", f"{mm['Calmar']:4.2f}"]
    yr = d["net"].groupby(d.index.year).apply(lambda x: (1 + x).prod() - 1)
    out.append(" ".join(f"{y}:{v*100:+.0f}" for y, v in yr.items()))
    out.append(f"to={d['turnover'].sum()/ (len(d)/365.25):.0f}x flips={d['flip'].sum()/(len(d)/365.25):.1f}")
    return " | ".join(out)

def trend_feat(n, kind="sma"):
    btc = c["BTC"]
    return btc / btc.rolling(n, min_periods=n).mean() - 1

def run_switch(n, Lalt, thr=0.0, Lbase=14, K=12, R=2, hyst=0.0):
    x = trend_feat(n).to_numpy()
    wa, _ = E.book(Lalt, K, R); wb, _ = E.book(Lbase, K, R)
    flag = np.isfinite(x) & (x > thr)
    w = np.where(flag[:, None], wa, wb)
    return finish(w)

def finish(w):
    delta = np.abs(np.diff(w, axis=0, prepend=np.zeros((1, w.shape[1])))).sum(axis=1)
    earned = np.vstack([np.zeros((1, w.shape[1])), w[:-1]])
    to = np.r_[0, delta[:-1]]
    gross = (earned * E.ret).sum(axis=1) - to * 0.001
    net = gross - (earned * E.funding.to_numpy()).sum(axis=1)
    idx = c.index; mask = idx >= pd.Timestamp("2022-01-01")
    rb = np.r_[False, (delta[:-1] > 0)]
    flipstate = np.zeros(len(w))
    d = pd.DataFrame({"net": net, "turnover": to, "gross": np.abs(earned).sum(1), "rebalance": rb,
                      "flip": False, "without_funding": gross}, index=idx).loc[mask]
    return {"daily": d}

if __name__ == "__main__":
    print("name | TRAIN cagr mdd cal | OOS | FULL | years | turnover")
    print(row("baseline 14/2/12", E.run(Config())))
    for L in (7, 10, 14, 21, 28, 35, 42):
        r = finish(E.book(L, 12, 2)[0]); print(row(f"static L={L}", r))
    for K in (6, 8, 12):
        for R in (2, 3, 5):
            r = finish(E.book(14, K, R)[0]); print(row(f"static 14/{R}/{K}", r))
    print("--- btc>SMA(n) -> Lalt else 14")
    for n in (50, 100, 150, 200, 250):
        for La in (21, 28, 35, 42):
            print(row(f"sma{n} up->L{La}", run_switch(n, La)))
    print("--- also long L when down, short up (inverse control)")
    for n in (200,):
        x = trend_feat(n).to_numpy(); wa, _ = E.book(28, 12, 2); wb, _ = E.book(14, 12, 2)
        flag = np.isfinite(x) & (x <= 0)
        print(row("INVERSE sma200 down->L28", finish(np.where(flag[:, None], wa, wb))))
    print("--- three-way: sma200 up->28 / down->7")
    x = trend_feat(200).to_numpy()
    for Ld in (7, 10, 14):
        w28 = E.book(28, 12, 2)[0]; wd = E.book(Ld, 12, 2)[0]
        flag = np.isfinite(x) & (x > 0)
        print(row(f"sma200 up->28 down->{Ld}", finish(np.where(flag[:, None], w28, wd))))


def run_rev(feat, thr, Lrev, Lbase=14, K=12, R=2, flat=False, rev_R=None, sign=-1):
    x = feat.to_numpy(); flag = np.isfinite(x) & (x < thr)
    wb = E.book(Lbase, K, R)[0]
    wr = E.book(Lrev, K, rev_R or R)[0] * sign
    if flat: wr = np.zeros_like(wr)
    return finish(np.where(flag[:, None], wr, wb))


def rev_study():
    btc = c["BTC"]
    feats = {"btc_mom14": btc.pct_change(14), "btc_mom7": btc.pct_change(7), "btc_mom30": btc.pct_change(30),
             "mkt_mom30": c.pct_change(30, fill_method=None).mean(axis=1)}
    print("--- reversal-sleeve neighbourhood")
    for name, ft in feats.items():
        for thr in (-0.05, -0.075, -0.1, -0.125, -0.15, -0.2):
            for Lr in (3, 5, 7):
                print(row(f"{name}<{thr} rev{Lr}", run_rev(ft, thr, Lr)))
    print("--- same but flat instead of reversal (is it the reversal or just flat?)")
    for thr in (-0.05, -0.1, -0.15):
        print(row(f"btc_mom14<{thr} FLAT", run_rev(feats["btc_mom14"], thr, 5, flat=True)))
    print("--- same but stay momentum-L28 instead")
    for thr in (-0.05, -0.1, -0.15):
        x = feats["btc_mom14"].to_numpy(); flag = np.isfinite(x) & (x < thr)
        w = np.where(flag[:, None], E.book(28, 12, 2)[0], E.book(14, 12, 2)[0]); print(row(f"btc_mom14<{thr} L28 mom", finish(w)))
    print("--- applied on static 14/3/12 and 14/3/8 bases")
    for R, K in ((3, 12), (3, 8), (5, 12)):
        print(row(f"base 14/{R}/{K}", finish(E.book(14, K, R)[0])))
        print(row(f"  +btc_mom14<-.1 rev5", run_rev(feats['btc_mom14'], -0.1, 5, K=K, R=R)))
        x = trend_feat(200).to_numpy(); flag = np.isfinite(x) & (x > 0)
        print(row(f"  +sma200 up->L28", finish(np.where(flag[:, None], E.book(28, K, R)[0], E.book(14, K, R)[0]))))
    print("--- combo: sma200 up->L28 else L14; and btc_mom14<-.1 -> rev5 overrides")
    x = trend_feat(200).to_numpy(); up = np.isfinite(x) & (x > 0)
    b = np.where(up[:, None], E.book(28, 12, 2)[0], E.book(14, 12, 2)[0])
    m14 = feats["btc_mom14"].to_numpy(); fl = np.isfinite(m14) & (m14 < -0.1)
    print(row("combo", finish(np.where(fl[:, None], -E.book(5, 12, 2)[0], b))))
    print("--- btc_mom14 rev: share of days flagged", float(fl[c.index >= '2022-01-01'].mean()))

if __name__ == "__main__":
    rev_study()
