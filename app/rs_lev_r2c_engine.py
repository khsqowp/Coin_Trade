"""R2-C research engine (offline, numba). V0 semantics of review/indep_sim.py + review/lambda_kill.py, extended with:
 - kill-fidelity lambda (hourly kill test on eq_close - lam*(eq_close - eq_antisync_worst)); hourly=0 -> V0 daily-close kill
 - per-run jitter: cooldown +-days and post-cooldown rebalance delay (indexed by kill ordinal k) -> breaks path merging
 - settlement of held positions when a symbol's data ends (delisting) and optional adverse shock events
 - liquidation diagnostics (never terminate the path): wick fraction f in (0.5, 0.75, 1.0) x maintenance model (tier, flat3),
   long adverse = ref - f*(ref-L), short adverse = ref + f*(H-ref) (ref = previous hourly close), maintenance on ADJUSTED-price notional
 - symbol column mask per run (subset stress)
Pure research code: no network, no live imports."""
import numpy as np
from numba import njit, prange

# parameter columns
(P_LEV, P_DEP, P_KILL, P_LAM, P_HOURLY, P_COOL, P_COST, P_K, P_REBAL, P_PHASE, P_D0, P_D1, P_N) = range(13)
# output columns
(O_FINAL, O_KILLS, O_ACTIVE, O_MAXGR, O_MEANGR, O_SETTLE, O_B0, O_B1, O_B2, O_B3, O_B4, O_B5, O_C0, O_C1, O_C2, O_C3,
 O_C4, O_C5, O_RUIN, O_D0, O_D1, O_D2, O_D3, O_D4, O_D5, O_N) = range(26)
RUIN_FINAL = 0.01   # AMENDMENT-1: path terminated when close-equity <= 0; recorded as final equity 0.01 (ln W floor)
# buffers: index = fi*2 + model  with fi over f=(0.5,0.75,1.0), model 0=tier(r1) 1=flat3
FRACS = (0.5, 0.75, 1.0)
MAXK = 96


def make_par(lev=4.0, dep=0.95, kill=0.35, lam=0.0, hourly=1, cool=14, cost=0.001, K=8, rebal=3, phase=0, d0=0, d1=0):
    return np.array([lev, dep, kill, lam, hourly, cool, cost, K, rebal, phase, d0, d1], dtype=np.float64)


@njit(cache=True)
def _one(H, L, C, FD, score, crash, r1, colmask, par, jcd, jph, evd, evml, evms, eqd, kdays, out, psym):
    nd, _, n = C.shape
    lev = par[0]; dep = par[1]; kill = par[2]; lam = par[3]; hourly = par[4] > 0.5
    cool0 = int(par[5]); cost = par[6]; K = int(par[7]); rebal = int(par[8]); phase = int(par[9])
    d0 = int(par[10]); d1 = int(par[11])
    q = np.zeros(n); e = np.zeros(n); lastpx = np.full(n, np.nan)
    ref = np.zeros(n); cl = np.zeros(n); Lh = np.zeros(n); Hh = np.zeros(n)
    W = 1.0; hwm = 1.0
    halted = False; halt_day = -1; last_reb = -1000000000; prev_flag = False
    kills = 0; cur_cool = cool0
    minbuf = np.full(6, 1e18); cntbuf = np.zeros(6); minday = np.full(6, -1)
    maxgr = 0.0; sumgr = 0.0; ngr = 0; nsettle = 0; prev_eq = 1.0; active = 0; ruined = False
    px = np.zeros(n); side = np.zeros(n)
    for i in range(d0, d1):
        eqd[i] = np.nan
        held = False
        for j in range(n):
            if q[j] != 0.0:
                held = True
                break
        killed = False
        if held:
            # ---- shocks / settlement of symbols whose data ended
            for j in range(n):
                if q[j] == 0.0:
                    continue
                settle = -1.0
                if evd[j] == i:
                    lp = lastpx[j] if np.isfinite(lastpx[j]) else e[j]
                    settle = lp * (evml[j] if q[j] > 0 else evms[j])
                else:
                    anyf = False
                    for h in range(24):
                        if np.isfinite(C[i, h, j]):
                            anyf = True
                            break
                    if not anyf:
                        settle = lastpx[j] if np.isfinite(lastpx[j]) else e[j]
                if settle >= 0.0:
                    psym[j] += q[j] * (settle - e[j])
                    W += q[j] * (settle - e[j]) - abs(q[j]) * settle * cost
                    q[j] = 0.0; e[j] = 0.0; nsettle += 1
            for j in range(n):
                if q[j] != 0.0:
                    f_ = FD[i, j]
                    if np.isfinite(f_):
                        W -= q[j] * f_
            for j in range(n):
                p0 = C[i - 1, 23, j] if i > 0 else np.nan
                ref[j] = p0 if np.isfinite(p0) else (lastpx[j] if np.isfinite(lastpx[j]) else e[j])
            for h in range(24):
                pc = 0.0; pw = 0.0
                Pref = 0.0; Pd = 0.0; Nref = 0.0; Nd = 0.0; Mref = 0.0; Md = 0.0; Fn = 0.0
                for j in range(n):
                    qj = q[j]
                    if qj == 0.0:
                        continue
                    c_ = C[i, h, j]
                    c_ = c_ if np.isfinite(c_) else e[j]
                    cl[j] = c_
                    if qj > 0:
                        x = L[i, h, j]
                    else:
                        x = H[i, h, j]
                    x = x if np.isfinite(x) else c_
                    pc += qj * (c_ - e[j])
                    pw += qj * (x - e[j])
                    aq = abs(qj)
                    rf = ref[j]
                    Pref += qj * (rf - e[j]); Pd += qj * (x - rf)
                    Nref += aq * rf; Nd += aq * (x - rf)
                    Mref += aq * rf * r1[j]; Md += aq * (x - rf) * r1[j]
                pe = prev_eq if prev_eq > 1e-9 else 1e-9
                for fi in range(3):
                    fr = 0.5 if fi == 0 else (0.75 if fi == 1 else 1.0)
                    marg = W + Pref + fr * Pd
                    nt = Nref + fr * Nd
                    b0 = (marg - (Mref + fr * Md)) / pe
                    b1 = (marg - 0.03 * nt) / pe
                    if b0 < minbuf[fi * 2]:
                        minbuf[fi * 2] = b0; minday[fi * 2] = i
                    if b1 < minbuf[fi * 2 + 1]:
                        minbuf[fi * 2 + 1] = b1; minday[fi * 2 + 1] = i
                    if b0 <= 0.0:
                        cntbuf[fi * 2] += 1.0
                    if b1 <= 0.0:
                        cntbuf[fi * 2 + 1] += 1.0
                if W + pc <= 0.0:
                    ruined = True
                    break
                if hourly and kill < 1.5:
                    pl = pc - lam * (pc - pw)
                    if 1.0 - (W + pl) / hwm >= kill:
                        cst = 0.0
                        for j in range(n):
                            if q[j] != 0.0:
                                cst += abs(q[j]) * cl[j] * cost
                        W += pl - cst
                        for j in range(n):
                            if q[j] != 0.0:
                                psym[j] += q[j] * (cl[j] - e[j])
                            q[j] = 0.0; e[j] = 0.0
                        halted = True; halt_day = i
                        if kills < MAXK:
                            kdays[kills] = i
                        kills += 1
                        killed = True
                        eqd[i] = W
                        break
                    if W + pc > hwm:
                        hwm = W + pc
                for j in range(n):
                    if q[j] != 0.0:
                        ref[j] = cl[j]
            if ruined:
                break
            if killed and W <= 0.0:
                ruined = True
                break
            if killed:
                prev_eq = W
                cur_cool = cool0 + int(jcd[min(kills - 1, MAXK - 1)])
                continue
        # ---- day close
        gross = 0.0
        for j in range(n):
            v = C[i, 23, j]
            if np.isfinite(v):
                px[j] = v
                lastpx[j] = v
            else:
                px[j] = lastpx[j] if np.isfinite(lastpx[j]) else (e[j] if e[j] > 0 else np.nan)
        eq = W
        for j in range(n):
            if q[j] != 0.0:
                eq += q[j] * (px[j] - e[j])
                gross += abs(q[j]) * px[j]
        eqd[i] = eq
        prev_eq = eq
        if eq <= 0.0:
            ruined = True
            break
        if held:
            active += 1
            g_ = gross / eq if eq > 1e-9 else 99.0
            if g_ > maxgr:
                maxgr = g_
            sumgr += g_; ngr += 1
        if eq > hwm:
            hwm = eq
        dd = 1.0 - eq / hwm
        if (not halted) and kill < 1.5 and dd >= kill:
            cst = 0.0
            for j in range(n):
                if q[j] != 0.0:
                    psym[j] += q[j] * (px[j] - e[j])
                    W += q[j] * (px[j] - e[j]); cst += abs(q[j]) * px[j] * cost
                    q[j] = 0.0; e[j] = 0.0
            W -= cst
            halted = True; halt_day = i
            if kills < MAXK:
                kdays[kills] = i
            kills += 1
            cur_cool = cool0 + int(jcd[min(kills - 1, MAXK - 1)])
            prev_eq = W
            continue
        if halted:
            if cur_cool > 0 and i - halt_day >= cur_cool:
                halted = False
                hwm = eq
                dl = int(jph[min(max(kills - 1, 0), MAXK - 1)])
                last_reb = i - rebal + dl
            else:
                continue
        flag = crash[i] > 0
        force = flag != prev_flag
        prev_flag = flag
        due = (i >= d0 + phase) and ((i - last_reb) >= rebal)
        if (not (due or force)) or i >= d1 - 1:
            continue
        cnt = 0
        for j in range(n):
            side[j] = 0.0
            if colmask[j] and np.isfinite(score[i, j]) and not (evd[j] >= 0 and i >= evd[j]):
                cnt += 1
        if cnt >= 2 * K and not flag:
            idx = np.empty(cnt, np.int64); vals = np.empty(cnt)
            m = 0
            for j in range(n):
                if colmask[j] and np.isfinite(score[i, j]) and not (evd[j] >= 0 and i >= evd[j]):
                    idx[m] = j; vals[m] = -score[i, j]; m += 1
            order = np.argsort(vals, kind="mergesort")
            for z in range(K):
                side[idx[order[z]]] = 1.0
            ns = 0
            for z in range(cnt - 1, -1, -1):
                if ns >= K:
                    break
                j = idx[order[z]]
                if side[j] == 0.0:
                    side[j] = -1.0; ns += 1
        elif cnt < 2 * K and not flag:
            continue
        tgt = eq * dep * lev / (2.0 * K)
        c_ = 0.0
        for j in range(n):
            sd = side[j]
            cs = 1.0 if q[j] > 0 else (-1.0 if q[j] < 0 else 0.0)
            if q[j] != 0.0 and sd == cs:
                continue
            if q[j] != 0.0:
                psym[j] += q[j] * (px[j] - e[j])
                W += q[j] * (px[j] - e[j]); c_ += abs(q[j]) * px[j] * cost
                q[j] = 0.0; e[j] = 0.0
            if sd != 0.0 and np.isfinite(px[j]) and px[j] > 0:
                qty = tgt / px[j]
                q[j] = sd * qty; e[j] = px[j]; c_ += qty * px[j] * cost
        W -= c_
        if due:
            last_reb = i
    for j in range(n):
        if q[j] != 0.0:
            pj = lastpx[j] if np.isfinite(lastpx[j]) else e[j]
            psym[j] += q[j] * (pj - e[j])
    fin = np.nan
    for i in range(d1 - 1, d0 - 1, -1):
        if np.isfinite(eqd[i]):
            fin = eqd[i]
            break
    if ruined:
        fin = RUIN_FINAL
    out[O_RUIN] = 1.0 if ruined else 0.0
    out[O_FINAL] = fin; out[O_KILLS] = kills; out[O_ACTIVE] = active; out[O_MAXGR] = maxgr
    out[O_MEANGR] = sumgr / ngr if ngr > 0 else 0.0; out[O_SETTLE] = nsettle
    for k in range(6):
        out[O_B0 + k] = minbuf[k]; out[O_C0 + k] = cntbuf[k]; out[O_D0 + k] = minday[k]


@njit(parallel=True, cache=True)
def run_batch(H, L, C, FD, score, crash, r1, colmask, PAR, JCD, JPH, EVD, EVML, EVMS, want_eq):
    """PAR (R,12); JCD/JPH (R,MAXK) int; colmask (R,n) uint8; EVD (R,n) int64 (-1 none); EVML/EVMS (R,n)."""
    R = PAR.shape[0]; nd = C.shape[0]
    OUT = np.zeros((R, O_N)); KD = np.full((R, MAXK), -1, dtype=np.int64); PS = np.zeros((R, C.shape[2]))
    EQ = np.full((R, nd if want_eq else 1), np.nan)
    for r in prange(R):
        eqd = np.full(nd, np.nan)
        _one(H, L, C, FD, score, crash, r1, colmask[r], PAR[r], JCD[r], JPH[r], EVD[r], EVML[r], EVMS[r], eqd, KD[r], OUT[r], PS[r])
        if want_eq:
            for i in range(nd):
                EQ[r, i] = eqd[i]
    return OUT, KD, EQ, PS


def jitter(R, seed, cd_span=2, ph_span=2):
    """Per-replicate jitter tables (common random numbers: same seed => same tables for every cell)."""
    rng = np.random.default_rng(seed)
    jcd = rng.integers(-cd_span, cd_span + 1, size=(R, MAXK)).astype(np.int64)
    jph = rng.integers(0, ph_span + 1, size=(R, MAXK)).astype(np.int64)
    return jcd, jph
