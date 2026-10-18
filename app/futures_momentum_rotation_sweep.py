"""모멘텀 로테이션 파라미터 강건성 체크 — 특정 파라미터 하나에 우연히 맞은 결과가 아닌지
lookback/리밸런스주기/롱숏개수를 조금씩 바꿔가며 연환산·MDD가 일관되게 나오는지 확인.
"""
from __future__ import annotations

import pandas as pd

from app.futures_data import fetch_perp_ohlcv
from app.futures_momentum_rotation_probe import UNIVERSE, SINCE, COMMISSION_PCT


def _fetch_closes() -> pd.DataFrame:
    series = {}
    for base in UNIVERSE:
        try:
            frame = fetch_perp_ohlcv(f"{base}/USDT:USDT", "1d", SINCE, None)
        except Exception:
            continue
        if frame.empty:
            continue
        series[base] = frame["Close"]
    return pd.DataFrame(series).sort_index()


def simulate(closes: pd.DataFrame, lookback: int, rebalance_every: int, top_k: int) -> tuple[float, float, float, int]:
    returns = closes.pct_change()
    momentum = closes.pct_change(lookback)
    dates = closes.index
    start_idx = lookback + 1
    weights = pd.Series(0.0, index=closes.columns)
    equity = 1.0
    peak = 1.0
    max_dd = 0.0
    last_weights = weights.copy()
    n_rebal = 0

    for i in range(start_idx, len(dates)):
        date = dates[i]
        day_ret = returns.loc[date]
        port_ret = (weights * day_ret.fillna(0.0)).sum()
        equity *= (1 + port_ret)
        peak = max(peak, equity)
        max_dd = max(max_dd, (peak - equity) / peak)

        if (i - start_idx) % rebalance_every == 0:
            mom_today = momentum.loc[date].dropna()
            mom_today = mom_today[closes.loc[date].notna()]
            if len(mom_today) >= top_k * 2:
                ranked = mom_today.sort_values(ascending=False)
                longs = ranked.index[:top_k]
                shorts = ranked.index[-top_k:]
                new_weights = pd.Series(0.0, index=closes.columns)
                new_weights[longs] = 0.5 / top_k
                new_weights[shorts] = -0.5 / top_k
                turnover = (new_weights - last_weights).abs().sum()
                equity *= (1 - turnover * COMMISSION_PCT / 100)
                weights = new_weights
                last_weights = new_weights.copy()
                n_rebal += 1

    years = (dates[-1] - dates[start_idx]).days / 365.25
    annualized_pct = ((equity) ** (1 / years) - 1) * 100 if years > 0 else float("nan")
    return annualized_pct, max_dd * 100, years, n_rebal


def run() -> None:
    print("종가 수집 중...")
    closes = _fetch_closes()
    print(f"{len(closes.columns)}개 종목, {len(closes)}행\n")

    print(f"{'lookback':>9}{'rebal':>7}{'top_k':>7}{'연환산':>9}{'MDD':>8}{'리밸런스':>9}")
    grid = []
    for lookback in [14, 30, 45, 60]:
        for rebalance in [3, 7, 14]:
            for top_k in [3, 5, 8]:
                ann, mdd, years, n = simulate(closes, lookback, rebalance, top_k)
                grid.append((lookback, rebalance, top_k, ann, mdd, n))
                print(f"{lookback:>9}{rebalance:>7}{top_k:>7}{ann:>8.2f}%{mdd:>7.1f}%{n:>9}")

    anns = [g[3] for g in grid]
    print(f"\n{len(grid)}개 조합 중 연환산>=10%: {sum(1 for a in anns if a >= 10)}개, "
          f"평균 {sum(anns)/len(anns):.2f}%, 중앙값 {sorted(anns)[len(anns)//2]:.2f}%, "
          f"최소 {min(anns):.2f}%, 최대 {max(anns):.2f}%")


if __name__ == "__main__":
    run()
