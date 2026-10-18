"""200/20일 스퀴즈 전략 공통 시뮬레이션+리포트 엔진 — 국장/미장/코인 러너가 이 함수 하나를
재사용한다. trx_buy_hold_wide_stop_backtest.py와 동일하게 백테스팅 라이브러리 없이 bar-by-bar
수동 시뮬레이션을 쓴다(전략이 단순해서 라이브러리 오버헤드가 필요없음).

포지션 크기는 매 진입마다 가용현금 전액(분할매수 없음) — 롱 온리(국장/미장은 계좌 구조상
숏이 안 되고, 코인도 다른 전략과 일관되게 롱만 다룬다)."""
from __future__ import annotations

import pandas as pd

from app.squeeze_indicators import add_squeeze_indicators

FEE_PCT_DEFAULT = 0.1
MIN_USABLE_BARS = 210  # SMA200이 유효값을 갖기 시작하는 지점 + 신호 관찰용 여유


def simulate(frame: pd.DataFrame, initial_capital: float, fee_pct: float = FEE_PCT_DEFAULT) -> dict | None:
    """데이터가 부족하면(SMA200을 못 채우면) None을 반환한다."""
    enriched = add_squeeze_indicators(frame).dropna(subset=["SMA200"])
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
            if bool(row["EXIT_SIGNAL"]):
                proceeds = qty * price * (1 - fee_pct / 100)
                cash += proceeds
                if price > entry_price:
                    wins += 1
                trades += 1
                qty = 0.0
                entry_price = None
        else:
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


def print_report(label: str, results: list[dict]) -> None:
    if not results:
        print(f"[{label}] 유효 결과 없음(전종목 데이터 부족 또는 조회 실패)")
        return

    results = sorted(results, key=lambda r: r["total_return_pct"], reverse=True)
    print(f"\n[{label} — 200/20일 스퀴즈 전략, {len(results)}종목 결과]")
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
    print(f"\n[{label} 요약] 유효 {len(results)}종목 중 수익 {positive}개({positive / len(results) * 100:.1f}%)")
    print(f"  평균 총수익률 {sum(rets) / len(rets):+.1f}%, 평균 연환산 {sum(ann) / len(ann):+.2f}%")
    print(f"  전체 매매횟수 {total_trades}건, 종목당 평균 {total_trades / len(results):.1f}건")
