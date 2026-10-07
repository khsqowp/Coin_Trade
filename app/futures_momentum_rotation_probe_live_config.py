"""모멘텀 로테이션 실물거래 실제 배포 설정(TOP_K=12, 레버리지4x, 2일 리밸런스,
배치80%, KILL_DD=35%/DELEVER_DD=20% 계좌단위 드로다운 제어, 포지션별 청산 근사)
백테스트. 기존 futures_momentum_rotation_probe.py(TOP_K=8, 1x, 3일)는 실제
배포값과 다른 설정이라 별도 검증 스크립트로 분리.

청산 근사: 일봉 종가 기준이라 장중 청산은 못 잡음 — 보수적(실제보다 청산을
적게 잡을 수 있음) 근사임을 전제로 함. 포지션은 진입 시점 레버리지로 거래소에
isolated 설정되므로(momentum_rotation_loop.py의 set_leverage(eff_lev,...)),
보유 중 청산 임계값은 진입 시점 eff_lev 기준 1/eff_lev 역행으로 근사.
"""
from __future__ import annotations

import pandas as pd

from app.futures_data import fetch_perp_ohlcv
from app.futures_momentum_rotation_probe import UNIVERSE, SINCE

MOMENTUM_LOOKBACK_DAYS = 14
REBALANCE_EVERY_DAYS = 2
TOP_K = 12
LEVERAGE = 4
DEPLOY_PCT = 0.8
KILL_DD = 0.35
DELEVER_DD = 0.20
COMMISSION_PCT = 0.04
START_CAPITAL_USDT = 10_000.0


def _fetch_closes() -> pd.DataFrame:
    series = {}
    for base in UNIVERSE:
        try:
            frame = fetch_perp_ohlcv(f"{base}/USDT:USDT", "1d", SINCE, None)
        except Exception as exc:  # noqa: BLE001
            print(f"  {base:6}: 수집실패 ({exc})")
            continue
        if frame.empty:
            continue
        series[base] = frame["Close"]
    return pd.DataFrame(series)


def run() -> None:
    print(f"[1/2] {len(UNIVERSE)}개 종목 종가 수집...")
    closes = _fetch_closes().sort_index()
    print(f"[2/2] 실물설정 시뮬레이션 (lookback {MOMENTUM_LOOKBACK_DAYS}일, "
          f"리밸런스 {REBALANCE_EVERY_DAYS}일마다, TOP_K={TOP_K}, 레버리지 {LEVERAGE}x, "
          f"배치 {DEPLOY_PCT*100:.0f}%, KILL_DD {KILL_DD*100:.0f}%, DELEVER_DD {DELEVER_DD*100:.0f}%)...")

    returns = closes.pct_change()
    momentum = closes.pct_change(MOMENTUM_LOOKBACK_DAYS)

    dates = closes.index
    start_idx = MOMENTUM_LOOKBACK_DAYS + 1

    weights = pd.Series(0.0, index=closes.columns)      # 현재 보유 비중(계좌 대비, 레버리지 반영)
    position_lev = {}                                    # base -> 진입 시점 eff_lev(청산 임계 계산용)
    equity = 1.0
    hwm = 1.0
    halted = False
    max_dd = 0.0
    equity_curve = []
    daily_returns = []
    n_rebalances = 0
    n_liquidations = 0
    n_delever_cycles = 0
    kill_triggered_at = None
    rebalance_equities = [1.0]
    last_rebalance_weights = weights.copy()

    for i in range(start_idx, len(dates)):
        date = dates[i]
        day_ret = returns.loc[date]

        dd_now = 1.0 - equity / hwm if hwm > 0 else 0.0
        if not halted and dd_now >= KILL_DD:
            halted = True
            kill_triggered_at = date
            weights[:] = 0.0
            position_lev = {}

        port_ret = 0.0
        if not halted:
            for base in list(position_lev.keys()):
                w = weights.get(base, 0.0)
                if w == 0.0:
                    continue
                r = day_ret.get(base, 0.0)
                if pd.isna(r):
                    r = 0.0
                lev = position_lev[base]
                adverse = -r if w > 0 else r
                if adverse >= 1.0 / lev:
                    port_ret += -abs(w) / lev
                    n_liquidations += 1
                    weights[base] = 0.0
                    del position_lev[base]
                else:
                    port_ret += w * r
            untracked = [b for b in weights.index if weights[b] != 0.0 and b not in position_lev]
            for base in untracked:
                r = day_ret.get(base, 0.0)
                if pd.isna(r):
                    r = 0.0
                port_ret += weights[base] * r

        equity *= (1 + port_ret)
        hwm = max(hwm, equity)
        max_dd = max(max_dd, 1.0 - equity / hwm if hwm > 0 else 0.0)
        daily_returns.append(port_ret)
        equity_curve.append((date, equity))

        if not halted and (i - start_idx) % REBALANCE_EVERY_DAYS == 0:
            dd_for_sizing = 1.0 - equity / hwm if hwm > 0 else 0.0
            eff_lev = 1 if (dd_for_sizing >= DELEVER_DD and LEVERAGE > 1) else LEVERAGE
            if eff_lev != LEVERAGE:
                n_delever_cycles += 1

            mom_today = momentum.loc[date].dropna()
            mom_today = mom_today[closes.loc[date].notna()]
            if len(mom_today) >= TOP_K * 2:
                ranked = mom_today.sort_values(ascending=False)
                longs = ranked.index[:TOP_K]
                shorts = ranked.index[-TOP_K:]

                deploy = DEPLOY_PCT
                per_pos = deploy * eff_lev / 2 / TOP_K

                new_weights = pd.Series(0.0, index=closes.columns)
                new_weights[longs] = per_pos
                new_weights[shorts] = -per_pos

                turnover = (new_weights - last_rebalance_weights).abs().sum()
                equity *= (1 - turnover * COMMISSION_PCT / 100)

                weights = new_weights
                position_lev = {b: eff_lev for b in list(longs) + list(shorts)}
                last_rebalance_weights = new_weights.copy()
                n_rebalances += 1
                rebalance_equities.append(equity)

    years = (dates[-1] - dates[start_idx]).days / 365.25
    total_return_pct = (equity - 1) * 100
    annualized_pct = ((equity) ** (1 / years) - 1) * 100 if years > 0 and equity > 0 else float("nan")

    print(f"\n기간: {dates[start_idx].date()} ~ {dates[-1].date()} ({years:.1f}년), 리밸런스 {n_rebalances}회")
    print(f"총수익률 {total_return_pct:.1f}%, 연환산 {annualized_pct:.2f}%, 최대낙폭(계좌HWM기준) {max_dd*100:.1f}%")
    print(f"포지션 청산(근사) 발생 {n_liquidations}건, 디레버 발동 사이클 {n_delever_cycles}회")
    if kill_triggered_at is not None:
        print(f"KILL_DD({KILL_DD*100:.0f}%) 도달 — {kill_triggered_at.date()} 이후 영구 정지(계좌 평탄화), "
              f"그 시점 이후 수익률 변화 없음")
    else:
        print(f"KILL_DD({KILL_DD*100:.0f}%) 도달 없음")

    daily_returns_s = pd.Series(daily_returns)
    sharpe = (daily_returns_s.mean() / daily_returns_s.std() * (365 ** 0.5)) if daily_returns_s.std() else float("nan")
    print(f"일간수익률 연환산 변동성: {daily_returns_s.std()*(365**0.5)*100:.1f}%, Sharpe(연) {sharpe:.2f}")

    period_returns = pd.Series(rebalance_equities).pct_change().dropna()
    wins = period_returns[period_returns > 0]
    losses = period_returns[period_returns < 0]
    win_rate = len(wins) / len(period_returns) * 100 if len(period_returns) else float("nan")
    print(f"\n[리밸런스 구간({REBALANCE_EVERY_DAYS}일) 단위 승률 {win_rate:.1f}% ({len(wins)}/{len(period_returns)})]")
    print(f"가상 시작자본 ${START_CAPITAL_USDT:,.0f} 기준 현재 자본: ${START_CAPITAL_USDT*equity:,.0f} "
          f"(누적손익 ${START_CAPITAL_USDT*(equity-1):+,.0f})")


if __name__ == "__main__":
    run()
