"""코인 실거래 후보 전략 비교 — 모멘텀 로테이션(14/3/8) 기반 가중치 레짐 × 포트폴리오 손절 × 배율.

가중치 레짐 (BTC 200일선 기준):
  neutral        : 항상 롱 0.5 / 숏 0.5 (현재 페이퍼 전략)
  regime_tilt    : BTC>200MA → 롱 0.7 / 숏 0.3,  아니면 0.5 / 0.5
  regime_longonly: BTC>200MA → 롱 1.0 / 숏 0.0,  아니면 0.5 / 0.5
  regime_cash    : BTC>200MA → 롱 1.0 / 숏 0.0,  아니면 전액 현금 (듀얼모멘텀)

포트폴리오 손절: 자본이 고점 대비 stop_pct 하락하면 전액 청산 후,
  BTC 가 200일선을 회복할 때까지(또는 최소 5거래일) 재진입 금지.

배율: 일간 수익률·수수료·펀딩드래그에 곱. 하루 손실이 (1/L - 유지증거금) 넘으면 청산 처리.

실행: docker run --rm --entrypoint python -v .../trading/app:/app/app \
        ochestration-trading-momentum-rotation -m app.crypto_strategy_showdown
"""
from __future__ import annotations

import itertools

import numpy as np
import pandas as pd

from app.futures_data import fetch_perp_ohlcv
from app.futures_momentum_rotation_probe import (
    COMMISSION_PCT, MOMENTUM_LOOKBACK_DAYS, REBALANCE_EVERY_DAYS, SINCE, TOP_K, UNIVERSE,
)

FUNDING_DRAG_PCT_PER_X = 4.0
MAINT_MARGIN = 0.005
REGIMES = ["neutral", "regime_tilt", "regime_longonly", "regime_cash"]
STOP_PCTS = [0.0, 0.15, 0.20, 0.25]
LEVERAGES = [1.0, 1.5, 2.0, 2.5]
STOP_MODES = ["none", "flatten", "delever"]


def _load() -> pd.DataFrame:
    series = {}
    for base in UNIVERSE:
        try:
            fr = fetch_perp_ohlcv(f"{base}/USDT:USDT", "1d", SINCE, None)
        except Exception:  # noqa: BLE001
            continue
        if not fr.empty:
            series[base] = fr["Close"]
    return pd.DataFrame(series).sort_index()


def _daily_series(closes: pd.DataFrame):
    """레짐별 일간 포트 수익률 + 회전율 + BTC>200MA 마스크."""
    returns = closes.pct_change()
    momentum = closes.pct_change(MOMENTUM_LOOKBACK_DAYS)
    btc = closes["BTC"]
    btc_bull = (btc > btc.rolling(200).mean())

    dates = closes.index
    start = max(MOMENTUM_LOOKBACK_DAYS + 1, 200)
    out = {r: {"ret": [], "turn": []} for r in REGIMES}
    idx = []
    last_w = {r: pd.Series(0.0, index=closes.columns) for r in REGIMES}
    cur_w = {r: pd.Series(0.0, index=closes.columns) for r in REGIMES}

    for i in range(start, len(dates)):
        d = dates[i]
        bull = bool(btc_bull.iloc[i])
        day_ret = returns.loc[d].fillna(0.0)
        idx.append(d)
        rebal = (i - start) % REBALANCE_EVERY_DAYS == 0
        mom = momentum.loc[d].dropna()
        mom = mom[closes.loc[d].notna()]
        for r in REGIMES:
            out[r]["ret"].append((cur_w[r] * day_ret).sum())
            turn = 0.0
            if rebal and len(mom) >= TOP_K * 2:
                ranked = mom.sort_values(ascending=False)
                longs, shorts = ranked.index[:TOP_K], ranked.index[-TOP_K:]
                lw, sw = 0.5, 0.5
                if r == "regime_tilt":
                    lw, sw = (0.7, 0.3) if bull else (0.5, 0.5)
                elif r == "regime_longonly":
                    lw, sw = (1.0, 0.0) if bull else (0.5, 0.5)
                elif r == "regime_cash":
                    lw, sw = (1.0, 0.0) if bull else (0.0, 0.0)
                nw = pd.Series(0.0, index=closes.columns)
                if lw:
                    nw[longs] = lw / TOP_K
                if sw:
                    nw[shorts] = -sw / TOP_K
                turn = (nw - last_w[r]).abs().sum()
                cur_w[r], last_w[r] = nw, nw.copy()
            out[r]["turn"].append(turn)
    res = {}
    for r in REGIMES:
        res[r] = (pd.Series(out[r]["ret"], index=idx), pd.Series(out[r]["turn"], index=idx))
    return res, btc_bull.reindex(idx)


def _sim(port: pd.Series, turn: pd.Series, bull: pd.Series, stop_pct: float, lev: float,
         stop_mode: str = "flatten") -> dict:
    years = (port.index[-1] - port.index[0]).days / 365.25
    base_fund = FUNDING_DRAG_PCT_PER_X / 100 / 365
    equity, peak, mdd, worst = 1.0, 1.0, 0.0, 0.0
    halted_days = 0
    delevered = False
    liq_on = None
    daily = []
    yearly: dict[int, float] = {}
    year_start_eq = {}

    for k, d in enumerate(port.index):
        yr = d.year
        if yr not in year_start_eq:
            year_start_eq[yr] = equity
        eff_lev = lev
        if stop_mode == "delever" and delevered:
            eff_lev = lev / 2

        if stop_mode == "flatten" and halted_days > 0:
            halted_days -= 1
            if halted_days == 0 and not bool(bull.iloc[k]):
                halted_days = 1
            peak = max(peak, equity)
            daily.append(0.0)
            yearly[yr] = equity / year_start_eq[yr] - 1
            continue

        fund_daily = base_fund * max(eff_lev - 1, 0)
        liq_th = 1.0 / eff_lev - MAINT_MARGIN
        g = port.iloc[k] * eff_lev - turn.iloc[k] * COMMISSION_PCT / 100 * eff_lev - fund_daily
        worst = min(worst, g)
        if g <= -liq_th and liq_on is None:
            equity, liq_on = 0.0, d.date()
            break
        equity *= (1 + g)
        daily.append(g)
        peak = max(peak, equity)
        dd = (peak - equity) / peak
        mdd = max(mdd, dd)
        yearly[yr] = equity / year_start_eq[yr] - 1

        if stop_pct > 0 and dd >= stop_pct:
            if stop_mode == "flatten":
                halted_days = 5
            elif stop_mode == "delever":
                delevered = True
        if stop_mode == "delever" and delevered and equity >= peak:
            delevered = False

    cagr = (equity ** (1 / years) - 1) * 100 if equity > 0 else -100.0
    calmar = cagr / (mdd * 100) if mdd > 0 else float("inf")
    dr = pd.Series(daily)
    sharpe = float(dr.mean() / dr.std() * np.sqrt(365)) if dr.std() > 0 else 0.0
    return {"cagr": cagr, "mdd": mdd * 100, "calmar": calmar, "sharpe": sharpe,
            "worst": worst * 100, "liq": liq_on, "final": equity,
            "yearly": {y: round(v * 100, 1) for y, v in sorted(yearly.items())}}


def run() -> None:
    print("종가 수집...")
    closes = _load()
    print(f"유효 {closes.shape[1]}종목, {closes.shape[0]}일. 레짐별 일간수익률 계산...")
    series, bull = _daily_series(closes)
    print(f"거래일 {len(bull)}일 ({bull.index[0].date()} ~ {bull.index[-1].date()}), "
          f"BTC 강세 비중 {bull.mean()*100:.0f}%\n")

    rows = []
    for regime, stop_mode, stop_pct, lev in itertools.product(REGIMES, STOP_MODES, STOP_PCTS, LEVERAGES):
        if stop_mode == "none" and stop_pct != 0.0:
            continue
        if stop_mode != "none" and stop_pct == 0.0:
            continue
        port, turn = series[regime]
        r = _sim(port, turn, bull, stop_pct, lev, stop_mode)
        r.update(regime=regime, stop=stop_pct, lev=lev, mode=stop_mode)
        rows.append(r)

    rows.sort(key=lambda x: (x["liq"] is not None, -x["calmar"]))
    print(f"{'레짐':<16} {'손절':>12} {'배율':>4} | {'CAGR':>8} {'MDD':>7} {'Calmar':>7} {'Sharpe':>7} {'최악일':>8} {'청산':>11}")
    print("-" * 100)
    for r in rows[:28]:
        liq = str(r["liq"]) if r["liq"] else "-"
        stop = "off" if r["mode"] == "none" else f"{r['mode']}/{r['stop']*100:.0f}%"
        print(f"{r['regime']:<16} {stop:>12} {r['lev']:>4.1f} | {r['cagr']:>+7.1f}% {r['mdd']:>6.1f}% "
              f"{r['calmar']:>7.2f} {r['sharpe']:>7.2f} {r['worst']:>+7.1f}% {liq:>11}")

    live = next(x for x in rows if x["regime"] == "neutral" and x["mode"] == "none" and x["lev"] == 1.0)
    print(f"\n현재 페이퍼(neutral/off/1배): CAGR {live['cagr']:+.1f}%, MDD {live['mdd']:.1f}%, "
          f"연도별 {live['yearly']}")
    print("\n[상위 6개 연도별 수익률 — 강건성 체크]")
    for r in rows[:6]:
        stop = "off" if r["mode"] == "none" else f"{r['mode']}/{r['stop']*100:.0f}%"
        print(f"  {r['regime']:<15} {stop:<12} {r['lev']}배: {r['yearly']}")
    print("\n가정: 펀딩드래그 연 4%/배율초과분, 유지증거금 0.5%, 슬리피지·부분체결 미반영. "
          "2022-07 시작(BTC 200일선 워밍업).")


if __name__ == "__main__":
    run()
