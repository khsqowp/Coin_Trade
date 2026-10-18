"""마하세븐 3기법 공통 시뮬레이션+리포트 엔진 — 국장/미장/코인 러너가 이 함수들을 재사용한다.
세 기법 모두 공통 규칙: 손익비 1.5 고정(손절폭 대비 익절폭 1.5배), 롱 온리.
"""
from __future__ import annotations

import pandas as pd

FEE_PCT_DEFAULT = 0.1
MIN_USABLE_BARS = 210  # 지표 계산에 필요한 충분한 데이터(EMA100 등)


def simulate(
    frame: pd.DataFrame,
    initial_capital: float,
    entry_signal_col: str = "ENTRY_SIGNAL",
    exit_signal_col: str = "EXIT_SIGNAL",
    stop_price_col: str = "STOP_PRICE",
    fee_pct: float = FEE_PCT_DEFAULT,
    risk_reward_ratio: float = 1.5,
    cooldown_bars: int = 3,
) -> dict | None:
    """마하세븐 기법 백테스트 시뮬레이션.

    entry_signal_col, exit_signal_col, stop_price_col는 지표모듈이 생성한 컬럼명.
    - 손절가가 진입가 이상이면(무효한 리스크) 그 신호는 건너뛴다.
    - 손절/익절 도달은 봉 내 저가/고가로 판정한다(종가만 보면 갭을 놓침).
    - 청산 후 cooldown_bars 봉 동안 재진입 금지(횡보장 과매매 방지).
    """
    enriched = frame.copy().dropna(subset=[entry_signal_col, exit_signal_col, stop_price_col])
    if len(enriched) < MIN_USABLE_BARS:
        return None

    has_hl = "High" in enriched.columns and "Low" in enriched.columns
    cash = initial_capital
    qty = 0.0
    entry_price: float | None = None
    stop_price: float | None = None
    tp_price: float | None = None
    trades = 0
    wins = 0
    cooldown = 0
    equity_points: list[tuple[pd.Timestamp, float]] = []

    for i in range(len(enriched)):
        row = enriched.iloc[i]
        price = float(row["Close"])
        low = float(row["Low"]) if has_hl else price
        high = float(row["High"]) if has_hl else price

        if qty > 0:  # 포지션 보유 중
            stop_hit = low <= stop_price
            tp_hit = high >= tp_price
            exit_signal = bool(row[exit_signal_col])

            if stop_hit or tp_hit or exit_signal:
                # 갭 하락이면 손절가보다 더 나쁜 종가에 체결될 수 있음 → min 처리
                exit_p = min(stop_price, price) if stop_hit else (tp_price if tp_hit else price)
                proceeds = qty * exit_p * (1 - fee_pct / 100)
                cash += proceeds
                if exit_p > entry_price:
                    wins += 1
                trades += 1
                qty = 0.0
                entry_price = stop_price = tp_price = None
                cooldown = cooldown_bars
        else:  # 포지션 없음
            if cooldown > 0:
                cooldown -= 1
            elif bool(row[entry_signal_col]):
                candidate_stop = float(row[stop_price_col])
                if candidate_stop < price:  # 유효한 손절만 진입
                    entry_price = price
                    stop_price = candidate_stop
                    tp_price = entry_price + (entry_price - stop_price) * risk_reward_ratio
                    qty = cash * (1 - fee_pct / 100) / price
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

    # 벤치마크: 같은 구간 buy&hold (첫 종가 매수 후 계속 보유)
    first_close = float(enriched["Close"].iloc[0])
    last_close = float(enriched["Close"].iloc[-1])
    bh_return_pct = (last_close / first_close - 1) * 100
    bh_annualized_pct = ((last_close / first_close) ** (1 / years) - 1) * 100 if last_close > 0 else -100.0
    bh_curve = enriched["Close"] / first_close
    bh_dd_pct = float(((bh_curve.cummax() - bh_curve) / bh_curve.cummax()).max() * 100)

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
        "bh_return_pct": bh_return_pct,
        "bh_annualized_pct": bh_annualized_pct,
        "bh_dd_pct": bh_dd_pct,
        "alpha_annualized_pct": annualized_pct - bh_annualized_pct,
    }


def print_report(label: str, results: list[dict]) -> None:
    """결과 테이블 출력."""
    if not results:
        print(f"[{label}] 유효 결과 없음(전종목 데이터 부족 또는 조회 실패)")
        return

    results = sorted(results, key=lambda r: r["alpha_annualized_pct"], reverse=True)
    print(f"\n[{label} — 마하세븐 눌림목 전략, {len(results)}종목 결과]")
    print(f"{'종목':<22} {'기간':>6} {'연환산':>9} {'B&H':>9} {'알파':>9} {'MDD':>8} {'매매':>5} {'승률':>7}")
    for r in results:
        name = r.get("display") or r.get("symbol")
        win_rate = f"{r['win_rate_pct']:.1f}%" if r["trades"] else "-"
        print(
            f"{name:<22} {r['years']:>4.1f}년 {r['annualized_pct']:>+8.2f}% {r['bh_annualized_pct']:>+8.2f}% "
            f"{r['alpha_annualized_pct']:>+8.2f}% {r['max_dd_pct']:>7.1f}% {r['trades']:>5} {win_rate:>7}"
        )

    ann = [r["annualized_pct"] for r in results]
    bh_ann = [r["bh_annualized_pct"] for r in results]
    alpha = [r["alpha_annualized_pct"] for r in results]
    positive = sum(1 for a in ann if a > 0)
    beat_bh = sum(1 for a in alpha if a > 0)
    total_trades = sum(r["trades"] for r in results)
    n = len(results)
    print(f"\n[{label} 요약] 유효 {n}종목")
    print(f"  전략 평균 연환산 {sum(ann) / n:+.2f}%  |  B&H 평균 연환산 {sum(bh_ann) / n:+.2f}%  |  평균 알파 {sum(alpha) / n:+.2f}%")
    print(f"  수익 종목 {positive}/{n}({positive / n * 100:.0f}%)  |  B&H 초과 종목 {beat_bh}/{n}({beat_bh / n * 100:.0f}%)")
    print(f"  전체 매매횟수 {total_trades}건, 종목당 평균 {total_trades / n:.1f}건")
