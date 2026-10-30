"""BACKTESTER-B analysis of rs_tp_b_run pickle. Writes docs/research/tp_loop/B/tables.md (generated) and prints the verdict checklist."""
import os, pickle, itertools, io
import numpy as np, pandas as pd
from math import sqrt, e as E
from scipy.stats import norm, skew, kurtosis
from app.rs_tp_b_run import GRID

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "research", "tp_loop", "B", "tables.md")
R = pickle.load(open(os.path.join(os.environ["RS_FINAL_SCRATCH"], "tp_b_res.pkl"), "rb"))
days = R["days"]; T = len(days)
IS = np.asarray(days <= pd.Timestamp("2024-06-30", tz="UTC")); OOS = ~IS
CFG = list(GRID)
buf = io.StringIO()
def P(*a):
    s = " ".join(str(x) for x in a); print(s); buf.write(s + "\n")

def sharpe(r): 
    sd = r.std(ddof=1); return float(r.mean() / sd * sqrt(365)) if sd > 0 else 0.0
def eqc(r): return np.cumprod(1 + r)
def mdd(r):
    eq = np.r_[1.0, eqc(r)]; return float(((np.maximum.accumulate(eq) - eq) / np.maximum.accumulate(eq)).max())
def cagr(r):
    end = eqc(r)[-1]; return float(end ** (365 / len(r)) - 1) if end > 0 else -1.0
def calmar(r):
    m = mdd(r); return cagr(r) / m if m > 0 else 0.0
def met(r): return dict(sh=sharpe(r), cagr=cagr(r), mdd=mdd(r), cal=calmar(r))
def win(o, mask, key): return [o[p]["ret"][mask] for p in range(3)]
def pm(o, mask):  # phase-mean/worst metrics
    ms = [met(x) for x in win(o, mask, "ret")]
    return {k: (float(np.mean([m[k] for m in ms])), float(np.min([m[k] for m in ms])), [m[k] for m in ms]) for k in ms[0]}
def sleeve(o): return np.mean([o[p]["ret"] for p in range(3)], axis=0)
ALL = np.ones(T, bool)
def imdd(o):
    out = []
    for x in o:
        eq = eqc(x["ret"]); pk = np.maximum.accumulate(np.r_[1.0, eq])[:-1]
        out.append(float(np.max(1 - x["worst"] / pk)))
    return float(np.mean(out)), float(np.max(out))

def get(sc, c): return R[(sc, c)]
def delta(sc, c, mask, base_sc=None):
    a = pm(get(sc, c), mask); b = pm(get(base_sc or sc, "V0"), mask)
    return dict(dsh=a["sh"][0] - b["sh"][0], dcal=a["cal"][0] - b["cal"][0],
                dsh_ph=[x - y for x, y in zip(a["sh"][2], b["sh"][2])], dcal_ph=[x - y for x, y in zip(a["cal"][2], b["cal"][2])])

P("# 생성 표 (app/rs_tp_b_analyze.py 자동 생성; 수치 수정 금지)\n")
# ---- 1. levels
P("## T1. V0 및 설정별 수준 지표 (lev4x0.95, 회계 C, 시간봉내 체결; 위상평균 [최악위상])\n")
P("| 설정 | 구간 | Sharpe | CAGR% | 종가MDD% | Calmar | 일중MDD%(평균/최악) | 평균노출 | kill/위상평균 |")
P("|---|---|---|---|---|---|---|---|---|")
for c in ["V0"] + CFG:
    o = get("main", c)
    for nm, mk in (("IS", IS), ("OOS", OOS), ("Full", ALL)):
        m = pm(o, mk)
        extra = ""
        if nm == "Full":
            a, b = imdd(o); extra = f"{a*100:.1f}/{b*100:.1f}"
        P(f"| {c} | {nm} | {m['sh'][0]:.2f} [{m['sh'][1]:.2f}] | {m['cagr'][0]*100:.1f} [{m['cagr'][1]*100:.1f}] | {m['mdd'][0]*100:.1f} [{max(m['mdd'][2])*100:.1f}] | {m['cal'][0]:.2f} [{m['cal'][1]:.2f}] | {extra} | {np.mean([x['expo'][mk].mean() for x in o]):.2f} | {np.mean([x['stats'][2] for x in o]):.1f} |")
# ---- 2. deltas
P("\n## T2. 변형-V0 차이 (위상평균; 괄호=전구간 위상별 dSharpe 0/1/2). 회계 C=cash, D=redeploy\n")
P("| 설정 | 회계 | dSh IS | dSh OOS | dSh Full | dCal IS | dCal OOS | dCal Full | 전구간 위상별 dSh | 위상 dSh>0 개수 |")
P("|---|---|---|---|---|---|---|---|---|---|")
D = {}
for sc, lab in (("main", "C"), ("redeploy", "D")):
    for c in CFG:
        d = {nm: delta(sc, c, mk) for nm, mk in (("IS", IS), ("OOS", OOS), ("Full", ALL))}
        D[(sc, c)] = d
        P(f"| {c} | {lab} | {d['IS']['dsh']:+.2f} | {d['OOS']['dsh']:+.2f} | {d['Full']['dsh']:+.2f} | {d['IS']['dcal']:+.2f} | {d['OOS']['dcal']:+.2f} | {d['Full']['dcal']:+.2f} | {'/'.join(f'{x:+.2f}' for x in d['Full']['dsh_ph'])} | {sum(x>0 for x in d['Full']['dsh_ph'])}/3 |")
P("\n보조 총노출 lev2x1.0 (결정 불사용):\n")
P("| 설정 | 회계 | dSh IS | dSh OOS | dSh Full | dCal Full |")
P("|---|---|---|---|---|---|")
for sc, lab in (("lev2", "C"), ("lev2_redeploy", "D")):
    for c in CFG:
        d = {nm: delta(sc, c, mk) for nm, mk in (("IS", IS), ("OOS", OOS), ("Full", ALL))}
        D[(sc, c)] = d
        P(f"| {c} | {lab} | {d['IS']['dsh']:+.2f} | {d['OOS']['dsh']:+.2f} | {d['Full']['dsh']:+.2f} | {d['Full']['dcal']:+.2f} |")
v2 = [pm(get("lev2", "V0"), m)["sh"][0] for m in (IS, OOS, ALL)]
P(f"\nlev2 V0 Sharpe IS/OOS/Full = {v2[0]:.2f}/{v2[1]:.2f}/{v2[2]:.2f}")

# ---- selection (IS only)
sel = {}
for sc in ("main", "redeploy", "lev2", "lev2_redeploy"):
    sel[sc] = max(CFG, key=lambda c: D[(sc, c)]["IS"]["dsh"])
P(f"\nIS 선택(IS dSharpe 최대): " + ", ".join(f"{k}->{v}" for k, v in sel.items()))
S0 = sel["main"]

# ---- 3. CPCV / PBO
def sh_mask(M, idx): 
    X = M[idx]; return X.mean(0) / X.std(0, ddof=1) * sqrt(365)
def cpcv(sc, selected, ng=6, emb=20):
    cols = ["V0"] + CFG
    M = np.stack([sleeve(get(sc, c)) for c in cols], 1)
    g = np.array_split(np.arange(T), ng)
    splits = list(itertools.combinations(range(ng), 2))
    res = []; lam = []; lam12 = []
    for sp in splits:
        te = np.concatenate([g[i] for i in sp])
        bad = np.zeros(T, bool)
        for i in sp:
            lo, hi = g[i][0], g[i][-1]; bad[max(0, lo - emb):min(T, hi + emb + 1)] = True
        tr = np.flatnonzero(~bad)
        s_tr = sh_mask(M, tr); s_te = sh_mask(M, te)
        b = int(np.argmax(s_tr)); rank = (s_te < s_te[b]).sum() + 1
        w = rank / (len(cols) + 1); lam.append(np.log(w / (1 - w)))
        s12tr, s12te = s_tr[1:], s_te[1:]; b2 = int(np.argmax(s12tr)); rk = (s12te < s12te[b2]).sum() + 1
        w2 = rk / (12 + 1); lam12.append(np.log(w2 / (1 - w2)))
        res.append((sp, b, te, s_te))
    pbo = float(np.mean(np.array(lam) <= 0)); pbo12 = float(np.mean(np.array(lam12) <= 0))
    # paths: group g -> p-th split containing g
    paths = []
    for p in range(ng - 1):
        v0, fx, cvch = [], [], []
        for gi in range(ng):
            idxs = [k for k, r in enumerate(res) if gi in r[0]]
            sp, b, te, _ = res[idxs[p]]
            v0.append(M[g[gi], 0]); fx.append(M[g[gi], cols.index(selected)]); cvch.append(M[g[gi], b])
        paths.append((sharpe(np.concatenate(v0)), sharpe(np.concatenate(fx)), sharpe(np.concatenate(cvch))))
    return pbo, pbo12, np.array(paths), res
P("\n## T3. CPCV (N=6 그룹, 검증 2그룹, 15분할, 경로 5개, purge/embargo 20일) 및 PBO\n")
P("| 회계 | 선택설정 | PBO(13열) | PBO(12열) | 경로별 Sharpe V0 | 경로별 Sharpe 선택(고정) | 경로별 Sharpe CV선택 | 경로 dSh(고정-V0) | 경로 dSh>0 | dSh(CV선택-V0)>0 |")
P("|---|---|---|---|---|---|---|---|---|---|")
CP = {}
for sc, lab in (("main", "C"), ("redeploy", "D")):
    pbo, pbo12, paths, res = cpcv(sc, sel[sc]); CP[sc] = (pbo, pbo12, paths)
    f = lambda a: "/".join(f"{x:.2f}" for x in a)
    P(f"| {lab} | {sel[sc]} | {pbo:.2f} | {pbo12:.2f} | {f(paths[:,0])} | {f(paths[:,1])} | {f(paths[:,2])} | {f(paths[:,1]-paths[:,0])} | {(paths[:,1]>paths[:,0]).sum()}/5 | {(paths[:,2]>paths[:,0]).sum()}/5 |")
# per-config path dSharpe
P("\n각 설정을 고정했을 때 CPCV 경로 5개 중 dSharpe>0 개수 (회계 C):\n")
M = {c: sleeve(get("main", c)) for c in ["V0"] + CFG}
g6 = np.array_split(np.arange(T), 6)
rowsx = []
for c in CFG:
    grp = [sharpe(M[c][i]) - sharpe(M["V0"][i]) for i in g6]
    rowsx.append(f"{c}: 그룹별 dSh " + "/".join(f"{x:+.1f}" for x in grp) + f" (양 {sum(x>0 for x in grp)}/6)")
P("\n".join("- " + x for x in rowsx))


P("\n## T3b. 고정 설정의 15개 검증분할(2그룹 합) dSharpe 분포 (회계 C; 고정설정은 경로 5개가 동일하므로 분할 단위로 보조 보고)\n")
P("| 설정 | 평균 | 중앙값 | 양(+) 분할 | 최소 | 최대 |")
P("|---|---|---|---|---|---|")
_, _, _, res_c = cpcv("main", S0)
Mm = {c: sleeve(get("main", c)) for c in ["V0"] + CFG}
SPL = {}
for c in CFG:
    dd_ = np.array([sharpe(Mm[c][r[2]]) - sharpe(Mm["V0"][r[2]]) for r in res_c]); SPL[c] = dd_
    P(f"| {c} | {dd_.mean():+.2f} | {np.median(dd_):+.2f} | {(dd_>0).sum()}/15 | {dd_.min():+.2f} | {dd_.max():+.2f} |")

# ---- 4. bootstrap
rng = np.random.default_rng(20261030)
def boot_idx(n, L, B, size):
    nb = int(np.ceil(size / L)); st = rng.integers(0, n - L + 1, size=(B, nb))
    return (st[:, :, None] + np.arange(L)[None, None, :]).reshape(B, -1)[:, :size]
def boot_diff(base, var, L=15, B=2000, mask=None):
    ix = np.flatnonzero(mask) if mask is not None else np.arange(len(base))
    b = base[ix]; v = var[ix]; n = len(ix)
    idx = boot_idx(n, L, B, n)
    out = []
    for r in (b, v):
        X = r[idx]; sh = X.mean(1) / X.std(1, ddof=1) * sqrt(365)
        eq = np.cumprod(1 + X, axis=1); pk = np.maximum.accumulate(np.concatenate([np.ones((B, 1)), eq], 1), axis=1)[:, 1:]
        md = ((pk - eq) / pk).max(1); cg = eq[:, -1] ** (365 / n) - 1
        out.append((sh, cg / np.maximum(md, 1e-9)))
    return out[1][0] - out[0][0], out[1][1] - out[0][1]
P("\n## T4. 블록 부트스트랩 (블록15일, 2000회, 3위상평균 sleeve 시계열) 변형-V0 90% CI [5%,95%], p(차이>0)\n")
P("| 설정 | 회계 | dSharpe 점추정 | dSharpe CI | p>0 | dCalmar 점추정 | dCalmar CI | p>0 | CI 모두 0 제외(양) |")
P("|---|---|---|---|---|---|---|---|---|")
BS = {}
for sc, lab in (("main", "C"), ("redeploy", "D")):
    base = sleeve(get(sc, "V0"))
    for c in CFG:
        v = sleeve(get(sc, c))
        ds, dc = boot_diff(base, v)
        pt_s = sharpe(v) - sharpe(base); pt_c = calmar(v) - calmar(base)
        BS[(sc, c)] = (pt_s, np.percentile(ds, [5, 95]), (ds > 0).mean(), pt_c, np.percentile(dc, [5, 95]), (dc > 0).mean())
        b = BS[(sc, c)]
        ok = b[1][0] > 0 and b[4][0] > 0
        P(f"| {c} | {lab} | {pt_s:+.2f} | [{b[1][0]:+.2f},{b[1][1]:+.2f}] | {b[2]:.2f} | {pt_c:+.2f} | [{b[4][0]:+.2f},{b[4][1]:+.2f}] | {b[5]:.2f} | {'예' if ok else '아니오'} |")
P("\n선택 설정 블록길이 민감도(10/15/20) 및 IS/OOS 부트스트랩, 위상별 (회계 C):\n")
base = sleeve(get("main", "V0")); v = sleeve(get("main", S0))
for L in (10, 15, 20):
    ds, dc = boot_diff(base, v, L=L)
    P(f"- {S0} 블록{L}: dSh CI [{np.percentile(ds,5):+.2f},{np.percentile(ds,95):+.2f}], dCal CI [{np.percentile(dc,5):+.2f},{np.percentile(dc,95):+.2f}]")
for nm, mk in (("IS", IS), ("OOS", OOS)):
    ds, dc = boot_diff(base, v, mask=mk)
    P(f"- {S0} {nm}: dSh CI [{np.percentile(ds,5):+.2f},{np.percentile(ds,95):+.2f}], dCal CI [{np.percentile(dc,5):+.2f},{np.percentile(dc,95):+.2f}]")
for p in range(3):
    ds, dc = boot_diff(get("main", "V0")[p]["ret"], get("main", S0)[p]["ret"])
    P(f"- {S0} 위상{p}: dSh CI [{np.percentile(ds,5):+.2f},{np.percentile(ds,95):+.2f}], dCal CI [{np.percentile(dc,5):+.2f},{np.percentile(dc,95):+.2f}]")

# ---- 5. DSR
def dsr(r, sr_trials_daily, N):
    sr = r.mean() / r.std(ddof=1); n = len(r); sk = skew(r); ku = kurtosis(r, fisher=False)
    v = np.var(sr_trials_daily, ddof=1); g = 0.5772156649
    sr0 = sqrt(v) * ((1 - g) * norm.ppf(1 - 1 / N) + g * norm.ppf(1 - 1 / (N * E)))
    den = sqrt(max(1 - sk * sr + (ku - 1) / 4 * sr * sr, 1e-9))
    return float(norm.cdf((sr - sr0) * sqrt(n - 1) / den)), sr * sqrt(365), sr0 * sqrt(365), sk, ku
trial_sc = ("main", "redeploy", "lev2", "lev2_redeploy")
absr = []; dfr = []
for sc in trial_sc:
    b = sleeve(get(sc, "V0"))
    for c in CFG:
        v = sleeve(get(sc, c)); absr.append(v.mean() / v.std(ddof=1)); dd_ = v - b; dfr.append(dd_.mean() / dd_.std(ddof=1))
absr = np.array(absr); dfr = np.array(dfr)
P("\n## T5. Deflated Sharpe (Bailey-Lopez de Prado). 시행 N=48 사전등록(12설정x2회계x2총노출); 민감도 N=24, N=76(이웃28 포함)\n")
P("| 대상 | 시리즈 | N | 연율 SR | SR0(연율) | 왜도 | 첨도(raw) | DSR |")
P("|---|---|---|---|---|---|---|---|")
DS = {}
for sc in ("main", "redeploy"):
    sc_sel = sel[sc]; v = sleeve(get(sc, sc_sel)); b = sleeve(get(sc, "V0"))
    for nm, series, trials in (("절대", v, absr), ("차이(변형-V0)", v - b, dfr)):
        for N in (24, 48, 76):
            d, s, s0, sk, ku = dsr(series, trials, N)
            DS[(sc, nm, N)] = d
            P(f"| {sc_sel}({'C' if sc=='main' else 'D'}) | {nm} | {N} | {s:.2f} | {s0:.2f} | {sk:.2f} | {ku:.1f} | {d:.3f} |")
v0s = sleeve(get("main", "V0")); d, s, s0, sk, ku = dsr(v0s, absr, 48)
P(f"| V0 | 절대 | 48 | {s:.2f} | {s0:.2f} | {sk:.2f} | {ku:.1f} | {d:.3f} |")
oo = np.flatnonzero(OOS)
d, s, s0, sk, ku = dsr((sleeve(get("main", S0)) - v0s)[oo], dfr, 48)
P(f"| {S0}(C) OOS만 | 차이 | 48 | {s:.2f} | {s0:.2f} | {sk:.2f} | {ku:.1f} | {d:.3f} |")
P(f"\n(설정 간 연율 IR 분산: 차이시리즈 sd={np.std(dfr,ddof=1)*sqrt(365):.2f}, 절대 SR sd={np.std(absr,ddof=1)*sqrt(365):.2f}; 낮을수록 시행이 강상관=DSR 변별력 낮음)")

# ---- 6. neighbours
P("\n## T6. 이웃 강건성 (각 파라미터 x0.75, x1.25; 회계 C 위상평균 dSharpe IS / OOS / Full)\n")
P("| 설정 | 이웃 | dSh IS | dSh OOS | dSh Full | 중심 dSh IS/OOS | IS·OOS 모두 >0 |")
P("|---|---|---|---|---|---|---|")
def delta_obj(o, mask):
    a = pm(o, mask); b = pm(get("main", "V0"), mask); return a["sh"][0] - b["sh"][0]
NB = {}
for c in CFG:
    m, a, b_, vol = GRID[c]
    for key in [k for k in R if isinstance(k, tuple) and k[0] == "nbr" and k[1] == c]:
        o = R[key]
        d = [delta_obj(o, mk) for mk in (IS, OOS, ALL)]
        par = "k" if key[2] == "A" and m != 2 and m != 3 else ("s" if m == 3 else ("a" if key[2] == "A" else "b"))
        val = a * key[3] if key[2] == "A" else b_ * key[3]
        NB.setdefault(c, []).append(d)
        P(f"| {c} | {par}={val:.2f} | {d[0]:+.2f} | {d[1]:+.2f} | {d[2]:+.2f} | {D[('main',c)]['IS']['dsh']:+.2f}/{D[('main',c)]['OOS']['dsh']:+.2f} | {'예' if d[0]>0 and d[1]>0 else '아니오'} |")
# ---- 7. cost
P("\n## T7. 비용/체결 민감도 (전구간 위상평균 dSharpe = 변형 - 같은 시나리오의 V0; 괄호=dCalmar)\n")
P("| 설정 | base | 2x 비용 | next-bar 체결 | 펀딩 스트레스 | base IS | base OOS | 2x IS | 2x OOS |")
P("|---|---|---|---|---|---|---|---|---|")
CS = {}
for c in CFG:
    row = {}
    for sc in ("main", "cost2x", "nextbar", "fundstress"):
        d = delta(sc, c, ALL); row[sc] = d
    di = {sc: (delta(sc, c, IS), delta(sc, c, OOS)) for sc in ("main", "cost2x")}
    CS[c] = (row, di)
    P(f"| {c} | " + " | ".join(f"{row[sc]['dsh']:+.2f} ({row[sc]['dcal']:+.2f})" for sc in ("main", "cost2x", "nextbar", "fundstress")) +
      f" | {di['main'][0]['dsh']:+.2f} | {di['main'][1]['dsh']:+.2f} | {di['cost2x'][0]['dsh']:+.2f} | {di['cost2x'][1]['dsh']:+.2f} |")
P("\nV0 자체 Sharpe(전구간 위상평균): " + ", ".join(f"{sc}={pm(get(sc,'V0'),ALL)['sh'][0]:.2f}" for sc in ("main", "cost2x", "nextbar", "fundstress", "redeploy")))

# ---- 8. exit-quality
Cc = R["C_close"]; atr = R["atr"]
def fwd(i, j, s, m, base_px=None):
    if i + m >= Cc.shape[0]: return np.nan
    b = Cc[i, j] if base_px is None else base_px
    return s * (Cc[i + m, j] / b - 1)
def control(o_v0, p, m):
    """mean same-side sign-adjusted fwd return (day-close to day-close) of V0 held positions, indexed by day, side."""
    s_sum = {1: np.zeros(T), -1: np.zeros(T)}; s_cnt = {1: np.zeros(T), -1: np.zeros(T)}
    d0 = int(round(0))
    tl = o_v0[p]["trades"]
    off = None
    return tl
P("\n## T8. 익절 품질 진단 (회계 C, 시간봉내 체결; 3위상 합산)\n")
P("전량청산(TP/트레일) 및 부분청산(scale)의 청산 시점 이후 포지션 방향 수익률. 기준(control)=같은 날·같은 방향 V0 보유 포지션의 같은 구간 평균. 일 종가 기준(청산일 종가->+m일 종가).\n")
# d0 absolute offset: events day is absolute panel index; panel starting index = d_start
d_start = int(np.argmax(np.asarray(R["days"]) >= R["days"][0]))  # =0 (R days already sliced); abs index offset needed
EOFF = None
def run_diag():
    import app.rs_final_data as fd
    P0 = fd.load_panel(); dd0 = int(P0["days"].searchsorted(pd.Timestamp("2022-01-01", tz="UTC")))
    return dd0
OFF = run_diag()
v0o = get("main", "V0")
ctrl = {}
for m in (1, 3, 7):
    sm = {1: np.zeros(T), -1: np.zeros(T)}; cn = {1: np.zeros(T), -1: np.zeros(T)}
    for p in range(3):
        for (ed, xd, j, s, pn, ty) in v0o[p]["trades"]:
            for t in range(int(ed) - OFF + 1, int(xd) - OFF + 1):
                if 0 <= t < T and t + m < T and np.isfinite(Cc[t, int(j)]) and np.isfinite(Cc[t + m, int(j)]):
                    sm[int(s)][t] += s * (Cc[t + m, int(j)] / Cc[t, int(j)] - 1); cn[int(s)][t] += 1
    ctrl[m] = (sm, cn)
P("| 설정 | 유형 | 발동수(3위상 합) | 거래당 발동률 | 연당 발동(위상평균) | m | 청산후 평균수익(일종가기준) | control | 초과 | 초과 t | 계속상승비율 | 청산가기준 평균 | 초과/ATR |")
P("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
DG = {}
for c in CFG:
    evs = np.concatenate([get("main", c)[p]["events"] for p in range(3)]) if any(len(get("main", c)[p]["events"]) for p in range(3)) else np.zeros((0, 7))
    ntr = sum(len(get("main", c)[p]["trades"]) for p in range(3))
    yrs = T / 365
    nfull = len(evs)
    for m in (1, 3, 7):
        rows = []
        for (ei, h, j, s, px_, ty, fr) in evs:
            i = int(ei) - OFF; j = int(j); s = int(s)
            f1 = fwd(i, j, s, m); f2 = fwd(i, j, s, m, base_px=px_)
            sm, cn = ctrl[m]
            ctl = sm[s][i] / cn[s][i] if cn[s][i] > 0 else np.nan
            rows.append((f1, ctl, f2, atr[i, j] if np.isfinite(atr[i, j]) else np.nan))
        a = np.array(rows, float)
        ok = np.isfinite(a[:, 0]) & np.isfinite(a[:, 1])
        if ok.sum() < 5: continue
        ex = a[ok, 0] - a[ok, 1]
        t = ex.mean() / (ex.std(ddof=1) / sqrt(len(ex)))
        DG[(c, m)] = (a[ok, 0].mean(), a[ok, 1].mean(), ex.mean(), t, (a[ok, 0] > 0).mean())
        P(f"| {c} | {GRID[c][0]} | {nfull} | {nfull/ntr:.3f} | {nfull/3/yrs:.0f} | {m} | {a[ok,0].mean()*100:+.2f}% | {a[ok,1].mean()*100:+.2f}% | {ex.mean()*100:+.2f}% | {t:+.1f} | {(a[ok,0]>0).mean():.2f} | {np.nanmean(a[ok,2])*100:+.2f}% | {np.nanmean(ex/a[ok,3]):+.2f} |")
# ---- 9. tails
P("\n## T9. 거래 단위 꼬리 분석 (진입시 자산 대비 거래 순손익, 3위상 합산, 회계 C)\n")
P("| 설정 | 거래수 | 상위1% 기여(총순손익 대비) | 상위5% 기여 | 상위1%/총이익 | 상위5%/총이익 | 거래 왜도 | 승률 | 손익비(평균이익/평균손실) | 평균 거래손익% | 일수익 왜도 | 일수익 첨도 |")
P("|---|---|---|---|---|---|---|---|---|---|---|---|")
TAIL = {}
for c in ["V0"] + CFG:
    o = get("main", c); pnl = np.concatenate([o[p]["trades"][:, 4] for p in range(3)])
    srt = np.sort(pnl)[::-1]; tot = pnl.sum(); n1 = max(1, int(len(pnl) * .01)); n5 = max(1, int(len(pnl) * .05))
    w = pnl[pnl > 0]; l = pnl[pnl <= 0]
    r = sleeve(o)
    gp = pnl[pnl > 0].sum()
    TAIL[c] = dict(g1=srt[:n1].sum() / gp, g5=srt[:n5].sum() / gp, t1=srt[:n1].sum() / tot, t5=srt[:n5].sum() / tot, sk=skew(pnl), wr=(pnl > 0).mean(), po=w.mean() / abs(l.mean()), mean=pnl.mean())
    t = TAIL[c]
    P(f"| {c} | {len(pnl)} | {t['t1']:.2f} | {t['t5']:.2f} | {t['g1']:.3f} | {t['g5']:.3f} | {t['sk']:.2f} | {t['wr']:.3f} | {t['po']:.2f} | {t['mean']*100:+.3f} | {skew(r):.2f} | {kurtosis(r, fisher=False):.1f} |")
open(OUT, "w").write(buf.getvalue())

# ---- 10. verdict checklist
def checklist(sc):
    c = sel[sc]; d = D[(sc, c)]
    ck = {}
    ck["1 IS&OOS dSh>0,dCal>0"] = d["IS"]["dsh"] > 0 and d["OOS"]["dsh"] > 0 and d["IS"]["dcal"] > 0 and d["OOS"]["dcal"] > 0
    ck["2 phases dSh>0 3/3"] = all(x > 0 for x in d["Full"]["dsh_ph"])
    pbo, pbo12, paths = CP[sc]
    ck["3 CPCV paths>=3/5 & PBO<=.30"] = (paths[:, 1] > paths[:, 0]).sum() >= 3 and pbo <= 0.30
    nbs = NB.get(c, []) if sc == "main" else None
    ck["4 neighbours IS&OOS>0"] = (all(x[0] > 0 and x[1] > 0 for x in nbs) if nbs is not None else None)
    if sc == "main":
        ck["5 2x cost & next-bar dSh>0"] = CS[c][0]["cost2x"]["dsh"] > 0 and CS[c][0]["nextbar"]["dsh"] > 0
    else:
        ck["5 2x cost & next-bar dSh>0"] = None
    ck["6 DSR(diff,N=48)>=.95"] = DS[(sc, "차이(변형-V0)", 48)] >= 0.95
    b = BS[(sc, c)]
    ck["7 bootstrap CI lower>0 (Sh & Cal)"] = b[1][0] > 0 and b[4][0] > 0
    return c, ck
P_ = print
print("\n==== VERDICT CHECKLIST ====")
for sc in ("main",):
    c, ck = checklist(sc)
    print(sc, c)
    for k, v in ck.items(): print("  ", k, v)
neg = sum(1 for c in CFG if D[("main", c)]["IS"]["dsh"] < 0 and D[("main", c)]["OOS"]["dsh"] < 0)
print("configs with dSh<0 in both IS and OOS:", neg, "/12;  hurts-CI-upper<0:", BS[("main", S0)][1][1] < 0)
print("configs dSh>0 in both IS and OOS:", sum(1 for c in CFG if D[("main", c)]["IS"]["dsh"] > 0 and D[("main", c)]["OOS"]["dsh"] > 0))
