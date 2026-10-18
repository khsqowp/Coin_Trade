"""공돌투자자 눌림목 반등매매 공통 시뮬레이션+리포트 엔진 — 국장/코인 러너가 이 함수를
재사용한다. squeeze_backtest_core.py와 동일하게 백테스팅 라이브러리 없이 bar-by-bar
수동 시뮬레이션을 쓴다.

포지션 크기는 매 진입마다 가용현금 전액(분할매수 없음) — 롱 온리.
청산: (1) 이평선 재이탈 또는 (2) 손익비(기본 -3%/+6%) 중 먼저 도달하는 조건."""
from __future__ import annotations

import pandas as pd

from app.pullback_rebound_indicators import add_pullback_rebound_indicators

FEE_PCT_DEFAULT = 0.1
MIN_USABLE_BARS = 100  # SMA5 또는 SMA10을 충분히 형성하기 위한 최소 봉 수


def simulate(
    frame: pd.DataFrame,
    initial_capital: float,
    ma_length: int = 5,
    volume_filter_enabled: bool = False,
    volume_multiplier: float = 1.5,
    loss_pct: float = -3.0,
    profit_pct: float = 6.0,
    fee_pct: float = FEE_PCT_DEFAULT,
) -> dict | None:
    """데이터가 부족하면(MIN_USABLE_BARS를 못 채우면) None을 반환한다.

    Args:
        frame: OHLCV 데이터프레임
        initial_capital: 초기자본
        ma_length: 이평선 길이(5 또는 10)
        volume_filter_enabled: 거래대금 필터 적용 여부
        volume_multiplier: 거래대금 필터 배수(예: 1.5)
        loss_pct: 손절율(예: -3.0%)
        profit_pct: 익절율(예: 6.0%)
        fee_pct: 거래수수료(편도 %)

    Returns:
        백테스트 결과 딕셔너리 또는 None(데이터 부족 시).
    """
    enriched = add_pullback_rebound_indicators(
        frame,
        ma_length=ma_length,
        volume_filter_enabled=volume_filter_enabled,
        volume_multiplier=volume_multiplier,
    ).dropna(subset=[f"SMA{ma_length}"])

    if len(enriched) < MIN_USABLE_BARS:
        return None

    cash = initial_capital
    qty = 0.0
    entry_price: float | None = None
    trades = 0
    wins = 0
    equity_points: list[tuple[pd.Timestamp, float]] = []

    for i in range(len(enriched)):
        row = enriched.iloc[i]
        price = float(row["Close"])

        if qty > 0:
            # 포지션이 열려 있음 — 청산 조건 확인
            exit_by_ma = bool(row["EXIT_SIGNAL"])
            loss_hit = (price - entry_price) / entry_price * 100 < loss_pct
            profit_hit = (price - entry_price) / entry_price * 100 > profit_pct

            if exit_by_ma or loss_hit or profit_hit:
                proceeds = qty * price * (1 - fee_pct / 100)
                cash += proceeds
                if price > entry_price:
                    wins += 1
                trades += 1
                qty = 0.0
                entry_price = None
        else:
            # 포지션 없음 — 진입 신호 확인
            if bool(row["ENTRY_SIGNAL"]):
                qty = cash * (1 - fee_pct / 100) / price
                entry_price = price
                cash = 0.0

        equity_points.append((enriched.index[i], cash + qty * price))

    equity = pd.Series({d: e for d, e in equity_points}).sort_index()
    final_equity = float(equity.iloc[-1])
    total_return_pct = (final_equity / initial_capital - 1) * 100
    years = max((equity.index[-1] - equity.index[0]).days / 365.25, 1e-6)
    annualized_pct = (
        ((final_equity / initial_capital) ** (1 / years) - 1) * 100 if final_equity > 0 else -100.0
    )
    peak = equity.cummax()
    max_dd_pct = float(((peak - equity) / peak).max() * 100)
    win_rate_pct = (wins / trades * 100) if trades else float("nan")

    return {
        "bars": len(enriched),
        "start": enriched.index[0],
        "end": enriched.index[-1],
        "years": years,
        "total_return_pct": total_return_pct,
        "annualized_pct": annualized_pct,
        "max_dd_pct": max_dd_pct,
        "trades": trades,
        "win_rate_pct": win_rate_pct,
        "final_equity": final_equity,
    }


def print_report(label: str, config_name: str, results: list[dict]) -> None:
    """결과를 표 형식으로 출력한다."""
    if not results:
        print(f"[{label} — {config_name}] 유효 결과 없음(전종목 데이터 부족 또는 조회 실패)")
        return

    results = sorted(results, key=lambda r: r["total_return_pct"], reverse=True)
    print(f"\n[{label} — {config_name}, {len(results)}종목 결과]")
    print(f"{'종목':<22} {'기간':>6} {'총수익률':>10} {'연환산':>9} {'MDD':>8} {'매매':>5} {'승률':>7}")
    for r in results:
        name = r.get("display") or r.get("symbol")
        win_rate = f"{r['win_rate_pct']:.1f}%" if r["trades"] else "-"
        print(
            f"{name:<22} {r['years']:>4.1f}년 {r['total_return_pct']:>+9.1f}% {r['annualized_pct']:>+8.2f}% "
            f"{r['max_dd_pct']:>7.1f}% {r['trades']:>5} {win_rate:>7}"
        )

    rets = [r["total_return_pct"] for r in results]
    ann = [r["annualized_pct"] for r in results]
    positive = sum(1 for r in rets if r > 0)
    total_trades = sum(r["trades"] for r in results)
    print(f"\n[{label} — {config_name} 요약]")
    print(f"  유효 {len(results)}종목 중 수익 {positive}개({positive / len(results) * 100:.1f}%)")
    print(f"  평균 총수익률 {sum(rets) / len(rets):+.1f}%, 평균 연환산 {sum(ann) / len(ann):+.2f}%")
    print(f"  전체 매매횟수 {total_trades}건, 종목당 평균 {total_trades / len(results):.1f}건")
