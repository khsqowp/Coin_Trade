"""1만원 룰 데이트레이딩 백테스트 핵심 엔진.

고정 손실 한도(1만원 또는 해당 통화 등가) 기반으로:
- 포지션 크기 역산: 손실한도 ÷ (진입가 - 손절가) = 거래량
- 손절/익절: 정해진 손절폭, 비대칭 익절(더 긴 익절)
- 당일청산: 진입 당일에 모든 포지션 청산
- 일일 최대 진입 1회 옵션
- 매매일지: 승률, 손익비, 1만원룰 위반 거래 통계
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pandas as pd


@dataclass
class TenThousandRuleConfig:
    """1만원 룰 백테스트 설정."""

    max_loss_per_trade_usd: float = 10.0  # 거래당 최대 손실(USD 또는 환산액)
    stop_loss_pct: float = 2.0  # 손절폭 (%)
    take_profit_pct: float = 5.0  # 익절폭 (%, 비대칭 - 손절보다 더 큼)
    fee_pct: float = 0.1  # 거래 수수료 (%)
    max_entries_per_day: int = 1  # 일일 최대 진입 횟수 (None = 무제한)
    initial_capital_usd: float = 100.0  # 초기자본
    force_eod_exit: bool = True  # 장마감 강제 청산 (데이트레이딩)


@dataclass
class Trade:
    """매매 기록."""

    entry_date: datetime
    exit_date: datetime | None
    entry_price: float
    exit_price: float | None
    quantity: float
    entry_cash: float  # 차감된 현금
    exit_cash: float | None  # 회수된 현금
    trade_type: str  # "LONG" 또는 "SHORT"
    exit_reason: str  # "PROFIT", "STOP_LOSS", "MEAN_REVERSION", "EOD_EXIT", "PENDING"
    loss_exceeded_limit: bool  # 1만원룰 위반 여부


class TenThousandRuleBacktest:
    """1만원 룰 데이트레이딩 시뮬레이터."""

    def __init__(self, config: TenThousandRuleConfig):
        self.config = config
        self.cash = config.initial_capital_usd
        self.position: Trade | None = None  # 현재 포지션
        self.trades: list[Trade] = []
        self.daily_equity: list[tuple[datetime, float]] = []
        self.entries_today: int = 0
        self.last_entry_date: datetime | None = None

    def _can_enter_today(self, current_date: datetime) -> bool:
        """일일 최대 진입 제한 확인."""
        if self.config.max_entries_per_day is None:
            return True
        if self.last_entry_date is None or self.last_entry_date.date() != current_date.date():
            self.entries_today = 0
            self.last_entry_date = current_date
        return self.entries_today < self.config.max_entries_per_day

    def _calculate_position_size(self, entry_price: float) -> float:
        """1만원 손실 한도 기반 거래량 역산.

        position_size = max_loss / (entry_price - stop_loss_price)
        """
        stop_price = entry_price * (1 - self.config.stop_loss_pct / 100)
        price_distance = entry_price - stop_price
        if price_distance <= 0:
            return 0.0
        position_size = self.config.max_loss_per_trade_usd / price_distance
        # 가용 자본으로 제한
        max_affordable = self.cash * (1 - self.config.fee_pct / 100) / entry_price
        return min(position_size, max_affordable)

    def process_bar(
        self,
        bar_index: int,
        bar_date: datetime,
        open_price: float,
        high_price: float,
        low_price: float,
        close_price: float,
        entry_signal: bool,
        exit_signal: bool,
    ) -> dict:
        """한 봉에 대한 시뮬레이션 단계.

        Returns
        -------
        dict
            { "action": "ENTRY" | "EXIT" | "HOLD" | None,
              "reason": str,
              "position": Trade | None,
              "equity": float }
        """
        action_log = {
            "bar_index": bar_index,
            "bar_date": bar_date,
            "action": None,
            "reason": None,
            "position": None,
            "equity": self.cash,
        }

        # 포지션 보유 중 — 청산 조건 체크
        if self.position:
            exit_reason = None

            # 1) 손절 (저가 터치)
            if low_price <= self.position.entry_price * (1 - self.config.stop_loss_pct / 100):
                exit_price = self.position.entry_price * (1 - self.config.stop_loss_pct / 100)
                exit_reason = "STOP_LOSS"

            # 2) 익절 (고가 터치)
            elif high_price >= self.position.entry_price * (1 + self.config.take_profit_pct / 100):
                exit_price = self.position.entry_price * (1 + self.config.take_profit_pct / 100)
                exit_reason = "PROFIT"

            # 3) 기술적 청산신호 (평균복귀)
            elif exit_signal:
                exit_price = close_price
                exit_reason = "MEAN_REVERSION"

            # 4) 당일 장마감 강제청산 (다음 봉이 다른 날인 경우)
            elif self.config.force_eod_exit:
                # 현재 봉이 마지막 봉이거나 다음 봉이 새로운 날인지는 외부에서 체크하고 별도 호출 필요
                # 여기서는 스킵하고 process_eod_exit() 메서드로 처리
                exit_price = None
                exit_reason = None

            if exit_reason:
                self._close_position(bar_date, exit_price, exit_reason)
                action_log["action"] = "EXIT"
                action_log["reason"] = exit_reason
                action_log["position"] = self.position

        # 포지션 없음 — 진입 조건 체크
        if not self.position and entry_signal:
            if self._can_enter_today(bar_date):
                self._open_position(bar_date, open_price)
                action_log["action"] = "ENTRY"
                action_log["reason"] = "ENTRY_SIGNAL"
                action_log["position"] = self.position
                self.entries_today += 1

        # 자기자본 계산 (포지션 있으면 시장가 기준, 없으면 현금)
        total_equity = self.cash
        if self.position and not self.position.exit_date:
            position_value = self.position.quantity * close_price
            total_equity = self.cash + position_value - self.position.entry_cash

        action_log["equity"] = total_equity
        self.daily_equity.append((bar_date, total_equity))

        return action_log

    def _open_position(self, entry_date: datetime, entry_price: float):
        """포지션 진입."""
        qty = self._calculate_position_size(entry_price)
        entry_cost = qty * entry_price * (1 + self.config.fee_pct / 100)

        self.position = Trade(
            entry_date=entry_date,
            exit_date=None,
            entry_price=entry_price,
            exit_price=None,
            quantity=qty,
            entry_cash=entry_cost,
            exit_cash=None,
            trade_type="LONG",
            exit_reason="PENDING",
            loss_exceeded_limit=False,
        )
        self.cash -= entry_cost

    def _close_position(self, exit_date: datetime, exit_price: float, exit_reason: str):
        """포지션 청산."""
        if not self.position:
            return

        exit_proceeds = self.position.quantity * exit_price * (1 - self.config.fee_pct / 100)
        actual_loss = exit_proceeds - self.position.entry_cash
        loss_exceeded = actual_loss < -self.config.max_loss_per_trade_usd

        self.position.exit_date = exit_date
        self.position.exit_price = exit_price
        self.position.exit_cash = exit_proceeds
        self.position.exit_reason = exit_reason
        self.position.loss_exceeded_limit = loss_exceeded

        self.trades.append(self.position)
        self.cash += exit_proceeds
        self.position = None

    def force_eod_exit(self, exit_date: datetime, exit_price: float):
        """장마감 강제 청산."""
        if self.position and not self.position.exit_date:
            self._close_position(exit_date, exit_price, "EOD_EXIT")


def run_backtest(
    frame,
    config: TenThousandRuleConfig,
):
    """프레임 전체에 대해 백테스트 실행.

    Parameters
    ----------
    frame : pd.DataFrame
        지표가 계산된 OHLCV 프레임
        컬럼: Open, High, Low, Close, Volume,
              ENTRY_SIGNAL, EXIT_SIGNAL 포함
    config : TenThousandRuleConfig
        백테스트 설정

    Returns
    -------
    tuple[TenThousandRuleBacktest, list[Trade]]
        (시뮬레이터 인스턴스, 매매 기록 리스트)
    """
    import pandas as pd

    bt = TenThousandRuleBacktest(config)

    for i in range(len(frame)):
        row = frame.iloc[i]
        bar_date = pd.Timestamp(row.name).to_pydatetime() if hasattr(row.name, 'to_pydatetime') else row.name
        if isinstance(bar_date, pd.Timestamp):
            bar_date = bar_date.to_pydatetime()

        entry_sig = bool(row.get("ENTRY_SIGNAL", False))
        exit_sig = bool(row.get("EXIT_SIGNAL", False))

        bt.process_bar(
            bar_index=i,
            bar_date=bar_date,
            open_price=float(row["Open"]),
            high_price=float(row["High"]),
            low_price=float(row["Low"]),
            close_price=float(row["Close"]),
            entry_signal=entry_sig,
            exit_signal=exit_sig,
        )

    # 마지막에 남은 포지션 있으면 강제 청산
    if bt.position and not bt.position.exit_date:
        last_close = float(frame.iloc[-1]["Close"])
        last_date = pd.Timestamp(frame.index[-1]).to_pydatetime() if hasattr(frame.index[-1], 'to_pydatetime') else frame.index[-1]
        if isinstance(last_date, pd.Timestamp):
            last_date = last_date.to_pydatetime()
        bt.force_eod_exit(last_date, last_close)

    return bt, bt.trades
