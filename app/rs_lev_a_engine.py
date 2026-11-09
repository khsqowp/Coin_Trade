"""BACKTESTER-A (lev_loop) research engine. OFFLINE research only; never imported by live code.

Derived line-by-line from rs_final_engine._sim (see that file for the live-faithful semantics). Additions:
  kill_mode 0 = kill on UTC daily-close drawdown (legacy, bit-exact with rs_final_engine when liq_stop=1)
  kill_mode 3 = (AMENDMENT 1) trigger on hourly-CLOSE equity dd, exit at hourly close marks (optimistic bracket: 24 samples/day, misses wicks)
  kill_mode 2 = as 1 but HWM also ratchets on hourly BEST-case equity before each hourly worst-case test (max pessimism bound)
  kill_mode 1 = kill on HOURLY WORST-CASE equity (longs at L, shorts at H, simultaneous) vs a hourly-close HWM,
                exit marked at that hour's adverse prices (conservative; approximates the live 15 s equity poll)
  Explicit cross-margin liquidation checks every hour on worst-case margin balance <= maintenance margin:
     model TIER : per-position maintenance rate by USD notional bracket (A0 USD per 1.0 of equity)
     model FLAT : flat 3% of notional (conservative)
     legacy     : rs_final_engine daily check (0.5% of day-max-high notional)  [only used for parity]
  Liquidation does NOT stop the path (counterfactual continues) except legacy liq_stop=1 or equity <= 0 (ruin);
  the first event day and the minimum cushion (wc - maint)/prev_close_equity are recorded per model.
  Per-trade realized PnL log and per-symbol funding for concentration analysis.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from numba import njit

from app.rs_final_engine import Sim, params, zscore_signal  # noqa: F401
from app.rs_final_engine import (P_REBAL, P_K, P_LEV, P_DEPLOY, P_COST, P_MMR, P_KILL, P_BAND, P_VT, P_VLB, P_CAP,
                                 P_DESIGN, P_DLV, P_RLV, P_RESIZE, P_REARM, P_COOL, P_CW, P_MINN, P_EQ0, P_PHASE,
                                 P_FUND, P_DMULT, P_SAFE, P_KMIN, P_GN)

MAXTR = 60000
# stats vector indices
(S_ATT, S_SKIP, S_KILL, S_REB, S_LIQLEG, S_NPOS, S_LIQ_TIER, S_LIQ_FLAT, S_CUSH_TIER, S_CUSH_FLAT, S_RUIN, S_MDDI,
 S_NTR, S_LASTDAY, S_N) = range(15)


@njit(cache=True)
def _tier_rate(notional_usd):
    if notional_usd < 50000.0:
        return 0.005
    if notional_usd < 250000.0:
        return 0.01
    if notional_usd < 1000000.0:
        return 0.025
    return 0.05


@njit(cache=True)
def _sim_a(Hh, Ll, Cc, FD, score, flat_flag, pr, minn_j, step_j, d0, d1, kill_mode, liq_stop, a0usd, flat_rate,
           tr_sym, tr_pnl, tr_day, sym_fund):
    nd, _, n = Cc.shape
    rebal = int(pr[0]); K0 = int(pr[1]); lev0 = pr[2]; deploy = pr[3]; cost = pr[4]; mmr = pr[5]; kill = pr[6]
    band = int(pr[7]); cool = int(pr[16]); minn = pr[18]; W = pr[19]
    phase = int(pr[20]); fund_on = pr[21] > 0; gnorm = pr[25] > 0
    q = np.zeros(n); e = np.zeros(n)
    eq_c = np.full(nd, np.nan); eq_w = np.full(nd, np.nan); expo = np.zeros(nd)
    hwm = W; prev_eq = W
    halted = False; halt_day = -1
    last_reb = -10 ** 9
    n_att = 0; n_skip = 0; n_kill = 0; n_reb = 0; liq = False; npos_sum = 0.0; npos_cnt = 0
    prev_flag = False
    px = np.zeros(n)
    pxc = np.zeros(n)
    liq_tier_day = -1; liq_flat_day = -1; cush_tier = 1e9; cush_flat = 1e9; ruin = False; mddi = 0.0
    ntr = 0; last_day = d0
    s_wc = np.zeros(24); s_cl = np.zeros(24); s_bc = np.zeros(24)
    for i in range(d0, d1):
        last_day = i
        held_any = False
        for j in range(n):
            if q[j] != 0.0:
                held_any = True
                break
        fund = 0.0
        worst = W
        maint = 0.0
        killed_today = False
        if held_any:
            wmin = 1e300
            for j in range(n):
                pxc[j] = e[j]
            for h in range(24):
                s = 0.0
                sc = 0.0
                sb = 0.0
                for j in range(n):
                    if q[j] != 0.0:
                        a = Ll[i, h, j] if q[j] > 0 else Hh[i, h, j]
                        if np.isfinite(a):
                            s += q[j] * (a - e[j])
                        b_ = Hh[i, h, j] if q[j] > 0 else Ll[i, h, j]
                        if np.isfinite(b_):
                            sb += q[j] * (b_ - e[j])
                        c_h = Cc[i, h, j]
                        if np.isfinite(c_h):
                            pxc[j] = c_h
                        sc += q[j] * (pxc[j] - e[j])
                s_wc[h] = s; s_cl[h] = sc; s_bc[h] = sb
                if s < wmin:
                    wmin = s
            if fund_on:
                for j in range(n):
                    if q[j] != 0.0:
                        fund -= q[j] * FD[i, j]
                        sym_fund[j] += -q[j] * FD[i, j]
            worst = W + fund + wmin
            for j in range(n):
                if q[j] != 0.0:
                    mx = 0.0
                    for h in range(24):
                        v = Hh[i, h, j]
                        if np.isfinite(v) and v > mx:
                            mx = v
                    maint += abs(q[j]) * max(mx, e[j]) * mmr
            W += fund
            # ---- explicit hourly liquidation model (does not alter state)
            den = prev_eq if prev_eq > 1e-12 else 1e-12
            for h in range(24):
                mt = 0.0; mf = 0.0
                for j in range(n):
                    if q[j] != 0.0:
                        v = Hh[i, h, j]
                        if not np.isfinite(v):
                            v = pxc[j]
                        nt = abs(q[j]) * v
                        mt += nt * _tier_rate(nt * a0usd)
                        mf += nt * flat_rate
                wc_eq = W + s_wc[h]
                ct = (wc_eq - mt) / den; cf = (wc_eq - mf) / den
                if ct < cush_tier:
                    cush_tier = ct
                if cf < cush_flat:
                    cush_flat = cf
                if ct <= 0.0 and liq_tier_day < 0:
                    liq_tier_day = i
                if cf <= 0.0 and liq_flat_day < 0:
                    liq_flat_day = i
        if held_any and worst <= maint:
            liq = True
            if liq_stop > 0:
                eq_c[i] = 0.0; eq_w[i] = 0.0
                break
        # ---- hourly kill (intraday) : sequential over hours, HWM from hourly closes
        if held_any and kill_mode >= 1 and (not halted):
            ddw = 0.0
            for h in range(24):
                if kill_mode == 2:
                    be = W + s_bc[h]
                    if be > hwm:
                        hwm = be
                wc_eq = W + s_wc[h]
                if hwm > 0:
                    ddw = 1.0 - wc_eq / hwm
                    if ddw > mddi:
                        mddi = ddw
                trig = ddw
                if kill_mode == 3 and hwm > 0:
                    trig = 1.0 - (W + s_cl[h]) / hwm
                if kill < 1.0 and trig >= kill:
                    # exit at this hour's adverse marks (modes 1,2) or at the hourly close marks (mode 3)
                    c_ = 0.0
                    for j in range(n):
                        if q[j] != 0.0:
                            if kill_mode == 3:
                                a = e[j]
                                for hh in range(h + 1):
                                    cv = Cc[i, hh, j]
                                    if np.isfinite(cv):
                                        a = cv
                            else:
                                a = Ll[i, h, j] if q[j] > 0 else Hh[i, h, j]
                            if not np.isfinite(a):
                                a = e[j]
                            pnl = q[j] * (a - e[j])
                            W += pnl; c_ += abs(q[j]) * a * cost
                            if ntr < tr_sym.shape[0]:
                                tr_sym[ntr] = j; tr_pnl[ntr] = pnl; tr_day[ntr] = i; ntr += 1
                            q[j] = 0.0; e[j] = 0.0
                    W -= c_
                    halted = True; halt_day = i; n_kill += 1
                    killed_today = True
                    eq_c[i] = W; eq_w[i] = wc_eq if kill_mode != 3 else W
                    expo[i] = 0.0
                    if W <= 0.0:
                        ruin = True
                    prev_eq = W
                    break
                ce = W + s_cl[h]
                if ce > hwm:
                    hwm = ce
            if killed_today:
                if ruin:
                    break
                continue
        elif held_any:
            ddw = 0.0
            for h in range(24):
                wc_eq = W + s_wc[h]
                if hwm > 0:
                    ddw = 1.0 - wc_eq / hwm
                    if ddw > mddi:
                        mddi = ddw
        for j in range(n):
            v = Cc[i, 23, j]
            px[j] = v if np.isfinite(v) else (e[j] if e[j] > 0 else np.nan)
        eq = W
        gross_n = 0.0
        npos = 0
        for j in range(n):
            if q[j] != 0.0:
                eq += q[j] * (px[j] - e[j])
                gross_n += abs(q[j] * px[j])
                npos += 1
        eq_c[i] = eq; eq_w[i] = worst
        expo[i] = gross_n / max(eq, 1e-12)
        prev_eq = eq
        if eq <= 0.0:
            ruin = True
            eq_c[i] = 0.0
            break
        npos_sum += npos; npos_cnt += 1
        if eq > hwm:
            hwm = eq
        dd = 1.0 - eq / hwm
        # ---- kill / halt (daily close)
        if (not halted) and dd >= kill:
            c_ = 0.0
            for j in range(n):
                if q[j] != 0.0:
                    pnl = q[j] * (px[j] - e[j])
                    W += pnl; c_ += abs(q[j]) * px[j] * cost
                    if ntr < tr_sym.shape[0]:
                        tr_sym[ntr] = j; tr_pnl[ntr] = pnl; tr_day[ntr] = i; ntr += 1
                    q[j] = 0.0; e[j] = 0.0
            W -= c_
            halted = True; halt_day = i; n_kill += 1
            continue
        if halted:
            if cool > 0 and i - halt_day >= cool:
                halted = False
                hwm = eq; dd = 0.0
                last_reb = -10 ** 9
            else:
                continue
        # ---- decide rebalance
        want_flat = flat_flag[i] > 0
        force = False
        if want_flat != prev_flag:
            force = True
        prev_flag = want_flat
        due = (i >= d0 + phase) and ((i - last_reb) >= rebal)
        if not (due or force) or i >= d1 - 1:
            continue
        cnt = 0
        for j in range(n):
            if np.isfinite(score[i, j]):
                cnt += 1
        K = K0
        lev = lev0
        side = np.zeros(n)
        if cnt >= 2 * K0 and not want_flat:
            order = np.argsort(-np.where(np.isfinite(score[i]), score[i], -1e18))
            rank = np.empty(n, np.int64)
            for z in range(n):
                rank[order[z]] = z
            nl = 0; ns = 0
            for z in range(cnt):
                if nl >= K:
                    break
                j = order[z]
                if side[j] == 0.0:
                    side[j] = 1.0; nl += 1
            for z in range(cnt - 1, -1, -1):
                if ns >= K:
                    break
                j = order[z]
                if side[j] == 0.0:
                    side[j] = -1.0; ns += 1
        elif cnt < 2 * K0 and not want_flat:
            continue
        tgt = eq * deploy * lev / (2.0 * K)
        c_ = 0.0
        for j in range(n):
            s = side[j]
            cs = 1.0 if q[j] > 0 else (-1.0 if q[j] < 0 else 0.0)
            if q[j] != 0.0 and s == cs:
                continue
            if q[j] != 0.0:
                pnl = q[j] * (px[j] - e[j])
                W += pnl; c_ += abs(q[j]) * px[j] * cost
                if ntr < tr_sym.shape[0]:
                    tr_sym[ntr] = j; tr_pnl[ntr] = pnl; tr_day[ntr] = i; ntr += 1
                q[j] = 0.0; e[j] = 0.0
            if s != 0.0 and np.isfinite(px[j]) and px[j] > 0:
                n_att += 1
                qty = tgt / px[j]
                mn = max(minn, minn_j[j])
                if qty <= 0 or qty * px[j] < mn:
                    n_skip += 1
                    continue
                q[j] = s * qty; e[j] = px[j]
                c_ += qty * px[j] * cost
        W -= c_
        if due:
            last_reb = i
        n_reb += 1
    # open positions at the end: mark to last close for attribution
    for j in range(n):
        if q[j] != 0.0 and np.isfinite(px[j]) and ntr < tr_sym.shape[0]:
            tr_sym[ntr] = j; tr_pnl[ntr] = q[j] * (px[j] - e[j]); tr_day[ntr] = last_day; ntr += 1
    npos_avg = npos_sum / max(npos_cnt, 1)
    st = np.zeros(S_N)
    st[S_ATT] = n_att; st[S_SKIP] = n_skip; st[S_KILL] = n_kill; st[S_REB] = n_reb
    st[S_LIQLEG] = 1.0 if liq else 0.0; st[S_NPOS] = npos_avg
    st[S_LIQ_TIER] = liq_tier_day; st[S_LIQ_FLAT] = liq_flat_day
    st[S_CUSH_TIER] = cush_tier; st[S_CUSH_FLAT] = cush_flat
    st[S_RUIN] = 1.0 if ruin else 0.0; st[S_MDDI] = mddi; st[S_NTR] = ntr; st[S_LASTDAY] = last_day
    return eq_c, eq_w, expo, st


def stress_panel(P, k: float):
    """Scale hourly log-price moves by k (power transform per symbol, anchored at first valid close).
    Funding per unit qty is rescaled by the daily close price ratio (approximation; rates unchanged)."""
    H = P["H"].copy(); L = P["L"].copy(); C = P["C"].copy(); FD = P["FD"].copy()
    nd, _, n = C.shape
    for j in range(n):
        cj = C[:, :, j].reshape(-1)
        fin = np.where(np.isfinite(cj))[0]
        if len(fin) == 0:
            continue
        b = cj[fin[0]]
        for X in (H, L, C):
            X[:, :, j] = b * (X[:, :, j] / b) ** k
    r = C[:, 23, :] / P["C"][:, 23, :]
    FD = FD * np.where(np.isfinite(r), r, 1.0)
    out = dict(P)
    out.update(H=H, L=L, C=C, FD=FD)
    return out


class SimA(Sim):
    def run_a(self, lev, deploy, kill, cool=14, kill_mode=1, cost=0.001, rebal=3, K=8, phase=0, d0=None, d1=None,
              liq_stop=0, a0usd=10000.0, flat_rate=0.03, crash_flat=True, fund=1):
        pr = params(rebal=rebal, K=K, lev=lev, deploy=deploy, cost=cost, kill=kill, cool=cool, phase=phase, fund=fund)
        score = self.signal((14,), False)
        flag = self.crash.astype(np.float64) if crash_flat else np.zeros(self.nd)
        d0 = self.d_start() if d0 is None else d0
        d1 = self.nd if d1 is None else d1
        tr_sym = np.zeros(MAXTR, np.int64); tr_pnl = np.zeros(MAXTR); tr_day = np.zeros(MAXTR, np.int64)
        sym_fund = np.zeros(len(self.names))
        ec, ew, ex, st = _sim_a(self.H, self.L, self.C, self.FD, score, flag, pr, self.minj(0.0), self.step_j, d0, d1,
                                int(kill_mode), int(liq_stop), float(a0usd), float(flat_rate),
                                tr_sym, tr_pnl, tr_day, sym_fund)
        nt = int(st[S_NTR])
        return dict(eq=ec, worst=ew, expo=ex, st=st, d0=d0, d1=d1, kills=int(st[S_KILL]),
                    tr_sym=tr_sym[:nt].copy(), tr_pnl=tr_pnl[:nt].copy(), tr_day=tr_day[:nt].copy(),
                    sym_fund=sym_fund.copy())
