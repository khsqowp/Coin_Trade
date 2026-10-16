"""US 주식 일봉 백테스트 엔진 (코인 전략 이식 리서치). 로컬 KIS 캐시만 사용, 네트워크/주문 없음.

규칙: 신호는 t일 종가까지의 정보, 체결은 t+1일 종가(1일 지연, 미래참조 없음).
가격은 KIS MODP=1(수정주가) 캐시. 현금 이자 0% 가정(보수적).
실행: /opt/homebrew/bin/python3.12 (pandas, numpy)
"""
from __future__ import annotations

import glob
import os

import numpy as np
import pandas as pd

CACHE = os.environ.get("US_CACHE", "/Users/user/Desktop/CODE/Ochestration/.kis-cache")
ANN = 252


# ---------------------------------------------------------------- data
def load_panel() -> dict[str, pd.DataFrame]:
    cols = {}
    for f in sorted(glob.glob(f"{CACHE}/US_*.csv")):
        sym = os.path.basename(f)[3:-4]
        d = pd.read_csv(f, parse_dates=["timestamp"], index_col="timestamp")
        d.index = d.index.tz_localize(None).normalize() if d.index.tz is None else d.index.tz_convert(None).normalize()
        d = d[~d.index.duplicated(keep="last")]
        cols[sym] = d
    out = {}
    for k in ["Open", "High", "Low", "Close", "Volume"]:
        out[k] = pd.DataFrame({s: d[k] for s, d in cols.items()}).sort_index()
    return out


def ema(a: np.ndarray, span: int) -> np.ndarray:
    return pd.DataFrame(a).ewm(span=span, adjust=False).mean().values


# ---------------------------------------------------------------- metrics
def metrics(eq: pd.Series, turnover: float | None = None, cost: float | None = None) -> dict:
    eq = eq.dropna()
    if len(eq) < 30:
        return {}
    yrs = (eq.index[-1] - eq.index[0]).days / 365.25
    cagr = (eq.iloc[-1] / eq.iloc[0]) ** (1 / yrs) - 1 if eq.iloc[-1] > 0 else -1.0
    mdd = float((1 - eq / eq.cummax()).max())
    r = eq.pct_change().dropna()
    sh = float(r.mean() / r.std() * np.sqrt(ANN)) if r.std() > 0 else 0.0
    yr = eq.groupby(eq.index.year).apply(lambda s: s.iloc[-1] / s.iloc[0] - 1)
    # 해의 첫 값은 이전해 마지막 값 기준이 정확하므로 재계산
    last = eq.groupby(eq.index.year).last()
    prev = last.shift(1)
    prev.iloc[0] = eq.iloc[0]
    yr = last / prev - 1
    m = eq.resample("ME").last().pct_change().dropna()
    return {
        "cagr": float(cagr), "mdd": mdd, "calmar": float(cagr / mdd) if mdd > 0 else 0.0,
        "sharpe": sh, "worst_year": float(yr.min()), "worst_year_n": int(yr.idxmin()),
        "months_up": float((m > 0).mean()) if len(m) else 0.0,
        "turnover_x": turnover, "cost_drag": cost, "years": yrs,
        "yearly": {int(k): float(v) for k, v in yr.items()},
    }


def rebase(eq: pd.Series, start: str | None, end: str | None = None) -> pd.Series:
    s = eq.loc[start:end] if start else eq
    return s / s.iloc[0]


# ---------------------------------------------------------------- target-weight engine
def run_weights(r: np.ndarray, tgt: np.ndarray, fee: float, borrow: float = 0.0, lag: int = 1):
    """r: T x N 일수익률(NaN→0). tgt: T x N 목표비중(행 전체 NaN = 조정 없음), t일 종가에 결정,
    lag일 뒤 종가에 체결. 수량 유지(드리프트). 반환: equity(T), turnover(합), cost(합)."""
    T, N = r.shape
    v = np.zeros(N)
    cash = 1.0
    out = np.empty(T)
    tover = 0.0
    cost_sum = 0.0
    for t in range(T):
        v = v * (1.0 + r[t])
        short_notional = -v[v < 0].sum()
        cash -= short_notional * borrow / ANN
        eq = cash + v.sum()
        if t - lag >= 0 and not np.isnan(tgt[t - lag, 0]):
            target = np.nan_to_num(tgt[t - lag]) * eq
            trades = np.abs(target - v).sum()
            c = trades * fee
            cost_sum += c / max(eq, 1e-9)
            eq -= c
            v = np.nan_to_num(tgt[t - lag]) * eq
            cash = eq - v.sum()
            tover += trades / max(eq, 1e-9)
        out[t] = cash + v.sum()
    return out, tover, cost_sum


# ---------------------------------------------------------------- slot engine (event driven)
def run_slots(P: dict, entry: np.ndarray, score: np.ndarray, exit_sig: np.ndarray | None,
              max_slots: int, fee: float, sl_pct: float | None = None, tp_pct: float | None = None,
              stop_px: np.ndarray | None = None, tp_rr: float | None = None,
              short: bool = False, short_entry: np.ndarray | None = None,
              short_exit: np.ndarray | None = None, borrow: float = 0.0):
    """신호는 t 종가, 체결은 t+1 종가. 손절/익절은 t+1 일봉 고저가로 판정(손절 우선, 갭은 시가 체결).
    슬롯당 자본 = 진입시점 자기자본/max_slots."""
    O, H, L, C = P["Open"].values, P["High"].values, P["Low"].values, P["Close"].values
    T, N = C.shape
    cash = 1.0
    pos: dict[int, dict] = {}
    eq_curve = np.empty(T)
    trades = []
    tover = 0.0
    cost_sum = 0.0
    for t in range(T):
        # 1) 보유 종목 청산 판정 (오늘 일봉)
        for i in list(pos):
            p = pos[i]
            side = p["side"]
            if np.isnan(C[t, i]):
                continue
            o, h, l, c = O[t, i], H[t, i], L[t, i], C[t, i]
            px = None
            if side > 0:
                if p["stop"] is not None and l <= p["stop"]:
                    px = min(p["stop"], o)
                elif p["tp"] is not None and h >= p["tp"]:
                    px = max(p["tp"], o)
            else:
                if p["stop"] is not None and h >= p["stop"]:
                    px = max(p["stop"], o)
                elif p["tp"] is not None and l <= p["tp"]:
                    px = min(p["tp"], o)
            if px is None and t >= 1:
                sig = exit_sig[t - 1, i] if side > 0 else (short_exit[t - 1, i] if short_exit is not None else False)
                if sig:
                    px = c
            if px is not None:
                gross = p["qty"] * px
                if side > 0:
                    proceeds = gross * (1 - fee)
                    cash += proceeds
                else:
                    cash -= gross * (1 + fee)  # 숏 환매 (진입시 매도대금은 현금에 이미 포함)
                ref = eq_curve[t - 1] if t > 0 else 1.0
                cost_sum += gross * fee / ref
                tover += gross / ref
                ret = (px / p["entry"] - 1) * side
                trades.append(ret - 2 * fee)
                del pos[i]
        # 숏 차입료
        if borrow and pos:
            sn = sum(p["qty"] * C[t, i] for i, p in pos.items() if p["side"] < 0 and not np.isnan(C[t, i]))
            cash -= sn * borrow / ANN
        # 2) 진입 (어제 종가 신호 → 오늘 종가 체결)
        if t >= 1 and len(pos) < max_slots:
            eqv = cash + sum(p["qty"] * (C[t, i] if not np.isnan(C[t, i]) else p["entry"]) * p["side"]
                             for i, p in pos.items())
            cand = []
            sc = score[t - 1]
            for i in np.where(entry[t - 1])[0]:
                if i not in pos and not np.isnan(C[t, i]) and not np.isnan(sc[i]):
                    cand.append((sc[i], i, 1))
            if short and short_entry is not None:
                for i in np.where(short_entry[t - 1])[0]:
                    if i not in pos and not np.isnan(C[t, i]) and not np.isnan(sc[i]):
                        cand.append((abs(sc[i]), i, -1))
            cand.sort(reverse=True)
            for s, i, side in cand:
                if len(pos) >= max_slots:
                    break
                px = C[t, i]
                alloc = min(eqv / max_slots, cash if side > 0 else eqv / max_slots)
                if alloc <= 0:
                    break
                stop = tp = None
                if side > 0:
                    if sl_pct is not None:
                        stop = px * (1 - sl_pct)
                    if stop_px is not None:
                        sp = stop_px[t - 1, i]
                        if np.isnan(sp) or sp >= px:
                            continue
                        stop = sp
                    if tp_pct is not None:
                        tp = px * (1 + tp_pct)
                    if tp_rr is not None and stop is not None:
                        tp = px + tp_rr * (px - stop)
                else:
                    if sl_pct is not None:
                        stop = px * (1 + sl_pct)
                    if tp_pct is not None:
                        tp = px * (1 - tp_pct)
                qty = alloc / px
                c = alloc * fee
                if side > 0:
                    cash -= alloc + c
                else:
                    cash += alloc - c
                ref = eq_curve[t - 1] if t > 0 else 1.0
                cost_sum += c / ref
                tover += alloc / ref
                pos[i] = {"qty": qty, "entry": px, "side": side, "stop": stop, "tp": tp}
        # 3) 평가
        val = cash
        for i, p in pos.items():
            c = C[t, i]
            if np.isnan(c):
                c = p["entry"]
            val += p["qty"] * c * (1 if p["side"] > 0 else -1)
        eq_curve[t] = val
    return eq_curve, np.array(trades), tover, cost_sum
