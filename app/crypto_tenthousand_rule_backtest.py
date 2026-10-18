"""1만원 룰 데이트레이딩 — 암호화폐(코인) 1분봉 백테스트.

TRX/USDT 1분 캔들에서:
- 볼린저밴드(20,2) 돌파 기반 진입
- 이격도 역행(MA 복귀) 기반 청산
- 고정 손실 한도(기본 10 USDT) 기반 포지션 크기 역산
- 비대칭 손익비: 손절 2%, 익절 5%
- 당일청산(데이트레이딩, 하루 최대 1회 진입 선택가능)
"""
from __future__ import annotations

import pandas as pd

from app.bollinger_divergence_indicators import (
    add_bollinger_divergence_indicators,
    detect_entry_signals,
    detect_exit_signals,
)
from app.data import fetch_ohlcv
from app.tenthousand_rule_backtest_core import (
    TenThousandRuleBacktest,
    TenThousandRuleConfig,
    run_backtest,
)

SYMBOL = "TRX/USDT"
SINCE = "2024-01-01T00:00:00Z"  # 1분봉은 수년치 보다는 1년 정도로 제한
UNTIL = None

CONFIG = TenThousandRuleConfig(
    max_loss_per_trade_usd=10.0,  # 거래당 최대 손실 10 USDT
    stop_loss_pct=2.0,  # 손절 2%
    take_profit_pct=5.0,  # 익절 5% (비대칭)
    fee_pct=0.1,  # 바이낸스 spot 수수료 ~0.1%
    initial_capital_usd=100.0,
    max_entries_per_day=1,  # 하루 최대 1회 진입 (선택사항)
    force_eod_exit=True,  # 당일청산
)


def run() -> None:
    print(f"[1/3] {SYMBOL} 1분봉 데이터 수집 (since {SINCE})...")
    try:
        frame = fetch_ohlcv(SYMBOL, "1m", SINCE, UNTIL)
    except Exception as e:
        print(f"  ERROR: 데이터 수집 실패 — {e}")
        return

    if len(frame) < 50:
        print(f"  ERROR: 충분한 데이터 부족 (수집됨: {len(frame)} 봉)")
        return

    print(f"  수집 완료: {len(frame)} 봉 ({frame.index[0]} ~ {frame.index[-1]})")

    print(f"[2/3] 지표 계산 및 신호 생성...")
    frame = add_bollinger_divergence_indicators(frame, bb_length=20, bb_std=2.0, ma_length=20)
    frame = detect_entry_signals(frame)
    frame = detect_exit_signals(frame)
    frame = frame.dropna(subset=["BB_UPPER", "BB_LOWER", "DIVERGENCE"])
    print(f"  지표 계산 완료 ({len(frame)} 봉 사용)")

    print(f"[3/3] 1만원 룰 데이트레이딩 백테스트 실행...")
    bt, trades = run_backtest(frame, CONFIG)

    # 자기자본 곡선
    equity_series = pd.Series({d: e for d, e in bt.daily_equity})
    if len(equity_series) > 0:
        equity_series = equity_series.sort_index()

        # 분석
        total_return_pct = (equity_series.iloc[-1] / CONFIG.initial_capital_usd - 1) * 100
        years = (equity_series.index[-1] - equity_series.index[0]).total_seconds() / (365.25 * 86400)
        annualized_pct = (
            ((equity_series.iloc[-1] / CONFIG.initial_capital_usd) ** (1 / years) - 1) * 100
            if years > 0 else float("nan")
        )

        peak = equity_series.cummax()
        dd = (peak - equity_series) / peak
        max_dd_pct = dd.max() * 100

        n_trades = len(trades)
        n_wins = sum(1 for t in trades if (t.exit_cash or 0) > t.entry_cash)
        n_losses = sum(1 for t in trades if (t.exit_cash or 0) <= t.entry_cash)
        win_rate = (n_wins / n_trades * 100) if n_trades > 0 else 0.0

        # 손익비 (평균수익/평균손실)
        winning_trades = [t for t in trades if (t.exit_cash or 0) > t.entry_cash]
        losing_trades = [t for t in trades if (t.exit_cash or 0) <= t.entry_cash]

        avg_win = sum((t.exit_cash or 0) - t.entry_cash for t in winning_trades) / len(winning_trades) if winning_trades else 0.0
        avg_loss = sum((t.exit_cash or 0) - t.entry_cash for t in losing_trades) / len(losing_trades) if losing_trades else 0.0

        profit_factor = (
            abs(sum((t.exit_cash or 0) - t.entry_cash for t in winning_trades)) / abs(sum((t.exit_cash or 0) - t.entry_cash for t in losing_trades))
            if losing_trades else float("inf")
        )

        # 1만원 룰 위반
        rule_violations = sum(1 for t in trades if t.loss_exceeded_limit)

        # 출구 이유 분석
        exit_reason_counts = {}
        for t in trades:
            reason = t.exit_reason
            exit_reason_counts[reason] = exit_reason_counts.get(reason, 0) + 1

        print(f"\n" + "=" * 80)
        print(f"[1만원 룰 데이트레이딩 전략 — {SYMBOL} 1분봉 백테스트 결과]")
        print(f"=" * 80)

        print(f"\n[기간 및 설정]")
        print(f"  기간: {equity_series.index[0].date()} ~ {equity_series.index[-1].date()}")
        print(f"  초기자본: ${CONFIG.initial_capital_usd:.2f}")
        print(f"  손절폭: {CONFIG.stop_loss_pct:.1f}%, 익절폭: {CONFIG.take_profit_pct:.1f}%")
        print(f"  거래당 최대손실 한도: ${CONFIG.max_loss_per_trade_usd:.2f}")
        print(f"  수수료: {CONFIG.fee_pct:.2f}%, 일일 최대 진입: {CONFIG.max_entries_per_day}")

        print(f"\n[성과]")
        print(f"  최종 자본: ${equity_series.iloc[-1]:.2f}")
        print(f"  총수익률: {total_return_pct:+.2f}%")
        print(f"  연환산 수익률: {annualized_pct:+.2f}%")
        print(f"  최대낙폭(MDD): {max_dd_pct:.2f}%")

        print(f"\n[거래 통계]")
        print(f"  총 거래건수: {n_trades}")
        print(f"  승리: {n_wins}건, 패배: {n_losses}건")
        print(f"  승률: {win_rate:.1f}%")
        print(f"  평균 수익거래: ${avg_win:+.4f}")
        print(f"  평균 손실거래: ${avg_loss:+.4f}")
        print(f"  손익비(Profit Factor): {profit_factor:.2f}x" if profit_factor != float("inf") else "  손익비(Profit Factor): Inf (손실 거래 없음)")

        print(f"\n[1만원 룰 준수]")
        print(f"  1만원 룰 위반 거래: {rule_violations}건 ({rule_violations/n_trades*100:.1f}%)" if n_trades > 0 else f"  1만원 룰 위반 거래: 0건 (거래 없음)")

        print(f"\n[출구 이유 분포]")
        for reason, count in sorted(exit_reason_counts.items(), key=lambda x: x[1], reverse=True):
            pct = count / n_trades * 100
            print(f"  {reason:<20} {count:>3}건 ({pct:>5.1f}%)")

        print(f"\n[거래 로그 (최근 20건)]")
        print(f"{'진입날짜':<20} {'진입가':<12} {'청산날짜':<20} {'청산가':<12} {'손익':<10} {'이유':<15}")
        print("-" * 89)
        for t in trades[-20:]:
            entry_str = t.entry_date.strftime("%Y-%m-%d %H:%M") if t.entry_date else "N/A"
            exit_str = t.exit_date.strftime("%Y-%m-%d %H:%M") if t.exit_date else "PENDING"
            pnl = (t.exit_cash or 0) - t.entry_cash
            pnl_pct = (pnl / t.entry_cash * 100) if t.entry_cash > 0 else 0.0
            reason = t.exit_reason
            print(f"{entry_str:<20} {t.entry_price:<12.6f} {exit_str:<20} {t.exit_price or 0:<12.6f} {pnl:+.4f} ${reason:<15}")

        print(f"\n" + "=" * 80)
        print(f"주의: 1분봉 백테스트는 슬리피지, 주문 실패, 부분 체결 등 현실의 마이크로 구조를")
        print(f"반영하지 않습니다. 실제 거래 결과와 다를 수 있습니다.")
        print(f"=" * 80 + "\n")

    else:
        print("  ERROR: 매매 데이터 없음")


if __name__ == "__main__":
    run()
