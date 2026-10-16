"""KR 일봉 백테스트 엔진 (비중 기반 / 이벤트(슬롯) 기반). 미래참조 없음:
 종가 t 에서 신호 -> 다음 거래일 시가(t+1)에 체결. 갭(전일종가->시가)은 기존 보유분이 겪고,
 장중(시가->종가)은 새 비중이 겪는다. 비용: 수수료 0.015%/편도 + 슬리피지(종목별) + 매도세 0.18%."""
from __future__ import annotations

import numpy as np
import pandas as pd

COMM = 0.00015
TAX = 0.0018
BORROW_YR = 0.03  # 공매도 대차수수료 가정(이론용)


def _ffill(a):
    return pd.DataFrame(a).ffill().to_numpy()


def run_weights(P, target, vol_target=None, vol_cap=1.0, lock=None, shorts=False):
    """target: TxN 목표비중(행 전체 NaN = 변경 없음). 반환 dict(eq, turnover, cost)."""
    T, N = P.c.shape
    o, c = np.nan_to_num(_ffill(P.o)), np.nan_to_num(_ffill(P.c))
    gap = np.nan_to_num(P.o[1:] / P.c[:-1] - 1)
    intra = np.nan_to_num(P.c / P.o - 1)
    buy_c, sell_c = COMM + P.slip, COMM + P.slip + TAX
    v = np.zeros(N); cash = 1.0
    eq = np.ones(T); turn = 0.0; cost_sum = 0.0
    base_w = np.zeros(N); pending = None; s_applied = 1.0
    rets = []; ref = peak = 1.0; armed = False; lock_until = -1
    for t in range(1, T):
        v = v * (1 + gap[t - 1])
        E = cash + v.sum()
        if pending is not None:
            delta = pending * E - v
            delta[~P.tradable[t]] = 0.0
            buys, sells = np.clip(delta, 0, None), np.clip(-delta, 0, None)
            cost = (buys * buy_c).sum() + (sells * sell_c).sum()
            cash -= delta.sum() + cost
            v = v + delta
            turn += np.abs(delta).sum(); cost_sum += cost
            pending = None
        v = v * (1 + intra[t])
        if shorts:
            cash -= np.clip(-v, 0, None).sum() * BORROW_YR / 252
        Enew = cash + v.sum()
        eq[t] = Enew
        rets.append(Enew / E - 1 if E > 0 else 0.0)
        # ---- 종가 t 의사결정
        row = target[t]
        changed = not np.isnan(row).all()
        if changed:
            base_w = np.nan_to_num(row)
        s = 1.0
        if vol_target and len(rets) >= 20:
            sd = np.std(rets[-20:]) * np.sqrt(252)
            s = min(vol_cap, vol_target / sd) if sd > 1e-9 else vol_cap
        locked = False
        if lock:
            if t < lock_until:
                locked = True
            else:
                if lock_until == t and lock_until > 0:
                    ref = peak = Enew; armed = False
                peak = max(peak, Enew)
                if Enew >= ref * (1 + lock[0]):
                    armed = True
                if armed and Enew <= peak * (1 - lock[1]):
                    lock_until = t + lock[2]; locked = True
        if locked:
            pending = np.zeros(N); s_applied = 0.0
        elif changed or abs(s - s_applied) > 0.1 or s_applied == 0.0:
            pending = base_w * s; s_applied = s
    return {"eq": pd.Series(eq, index=P.dates), "turn": turn, "cost": cost_sum}


def run_events(P, entry, exit_sig, score, slots, sl=None, tp=None, gate=None):
    """entry/exit_sig: TxN bool(종가 t 신호), score: TxN 랭킹(클수록 우선), slots: 최대 동시 보유.
    진입 = 다음 시가, 슬롯당 현재 자산/slots. 손절/익절은 장중 터치(같은 날 둘 다면 손절 우선).
    시가 갭이 손절 아래/익절 위면 시가 체결."""
    T, N = P.c.shape
    o, c = np.nan_to_num(_ffill(P.o)), np.nan_to_num(_ffill(P.c))
    lo, hi = np.nan_to_num(_ffill(P.l)), np.nan_to_num(_ffill(P.h))
    buy_c, sell_c = COMM + P.slip, COMM + P.slip + TAX
    sh = np.zeros(N); epx = np.zeros(N); held = np.zeros(N, bool); flagged = np.zeros(N, bool)
    cash = 1.0; eq = np.ones(T); turn = 0.0; cost_sum = 0.0
    want = []; trades = []; exp_days = 0
    def sell(j, px):
        nonlocal cash, turn, cost_sum
        gross = sh[j] * px; cst = gross * sell_c[j]
        cash += gross - cst; turn += gross; cost_sum += cst
        trades.append((px / epx[j] - 1) - (buy_c[j] + sell_c[j]))
        sh[j] = 0; held[j] = False; flagged[j] = False
    for t in range(1, T):
        # 1) 시가: 플래그된 청산, 갭 손절/익절
        for j in np.where(held)[0]:
            if not P.tradable[t, j]:
                continue
            if flagged[j]:
                sell(j, o[t, j]); continue
            if sl and o[t, j] <= epx[j] * (1 - sl):
                sell(j, o[t, j])
            elif tp and o[t, j] >= epx[j] * (1 + tp):
                sell(j, o[t, j])
        # 2) 시가 진입
        if want:
            E = cash + (sh * o[t]).sum()
            for j in want:
                if held[j] or not P.tradable[t, j] or held.sum() >= slots:
                    continue
                alloc = min(E / slots, cash / (1 + buy_c[j]))
                if alloc <= 1e-9:
                    continue
                cst = alloc * buy_c[j]
                sh[j] = alloc / o[t, j]; epx[j] = o[t, j]; held[j] = True
                cash -= alloc + cst; turn += alloc; cost_sum += cst
            want = []
        # 3) 장중 손절/익절 (이번 시가에 막 산 것 포함)
        for j in np.where(held)[0]:
            if sl and lo[t, j] <= epx[j] * (1 - sl):
                sell(j, min(o[t, j], epx[j] * (1 - sl)))
            elif tp and hi[t, j] >= epx[j] * (1 + tp):
                sell(j, max(o[t, j], epx[j] * (1 + tp)))
        eq[t] = cash + (sh * c[t]).sum()
        if held.any():
            exp_days += 1
        # 4) 종가 의사결정
        flagged |= held & exit_sig[t]
        free = slots - int((held & ~flagged).sum())
        if free > 0 and (gate is None or gate[t]):
            cand = np.where(entry[t] & P.elig[t] & ~held)[0]
            if len(cand):
                sc = score[t, cand]
                cand = cand[np.argsort(-np.nan_to_num(sc, nan=-1e18), kind="stable")][:free]
                want = list(cand)
    tr = np.array(trades) if trades else np.array([np.nan])
    return {"eq": pd.Series(eq, index=P.dates), "turn": turn, "cost": cost_sum,
            "trades": len(trades), "win": float(np.mean(tr > 0)) if trades else float("nan"),
            "exposure": exp_days / T}


def metrics(res, P, a, b):
    """equity 시리즈의 [a,b] 구간(인덱스 위치) 성과."""
    eq = res["eq"].iloc[a:b + 1]
    r = eq / eq.iloc[0]
    yrs = (eq.index[-1] - eq.index[0]).days / 365.25
    cagr = r.iloc[-1] ** (1 / yrs) - 1 if r.iloc[-1] > 0 else -1.0
    mdd = float((1 - r / r.cummax()).max())
    yr = r.groupby(r.index.year).agg(["first", "last"])
    prev = r.groupby(r.index.year).last().shift(1).fillna(1.0)
    peryear = (yr["last"] / prev - 1).to_dict()
    full_years = {y: v for y, v in peryear.items()}
    out = {"cagr": cagr, "mdd": mdd, "calmar": cagr / mdd if mdd > 0 else np.nan,
           "worst_year": min(full_years.values()), "peryear": full_years, "years": yrs,
           "final": float(r.iloc[-1])}
    # 회전율/비용은 전 구간 합계를 구간 길이로 환산(근사)
    tot_years = (res["eq"].index[-1] - res["eq"].index[0]).days / 365.25
    avg_eq = float(res["eq"].mean())
    out["turnover_yr"] = res.get("turn", 0) / 2 / tot_years / avg_eq
    out["cost_yr"] = res.get("cost", 0) / tot_years / avg_eq
    for k in ("win", "trades", "exposure"):
        if k in res:
            out[k] = res[k]
    return out
