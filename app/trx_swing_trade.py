"""TRX 스윙 실계좌 매매 로직 — trx_buy_hold_wide_stop_backtest.py로 검증된 규칙 그대로.

  - 진입: EMA9/EMA21 골든크로스(전일 종가 기준, 일봉)에서 보유 USDT 전액으로 시장가 매수
  - 청산: 매수가 대비 -STOP_LOSS_PCT% 하락 시 시장가 전량 손절 (실시간 체크, 사이클마다)
  - 재진입: 손절 이후에도 다음 골든크로스가 나오면 다시 매수(반복)

임시(temporary) 전략 — 펀딩비 차익거래의 신규진입을 막아 자연 청산시킨 자금을 이 계좌에서
그대로 이어받아 쓴다. 별도 예산 상수를 두지 않고, 그때그때 실제 보유 USDT 잔고를 조회해서 쓴다.
"""
from __future__ import annotations

import os

from app.data import fetch_ohlcv
from app.more_indicators import add_ema_cross_indicators
from app.paper_exchange import spot_client
from app.trx_swing_state import load_state, log_event, now_iso, save_state

SYMBOL = "TRX/USDT"
STOP_LOSS_PCT = float(os.environ.get("TRX_SWING_STOP_LOSS_PCT", "12.0"))
BALANCE_FRACTION = float(os.environ.get("TRX_SWING_BALANCE_FRACTION", "0.95"))
MIN_NOTIONAL_USDT = float(os.environ.get("TRX_SWING_MIN_NOTIONAL_USDT", "10.0"))
SPOT_FEE_PCT = 0.1


def _fill_price(order: dict, fallback: float) -> float:
    price = order.get("average") or order.get("price")
    return float(price) if price else fallback


def _net_base_amount(order: dict, requested_amount: float) -> float:
    """실계좌 매수 수수료는 보통 매수한 자산 자체(TRX)에서 차감된다 — 요청 수량과 실제 보유
    수량이 다를 수 있어, 이후 전량매도 시 잔고부족으로 거절되지 않도록 실제 체결수량을 쓴다."""
    filled = order.get("filled")
    amount = float(filled) if filled else requested_amount
    fees = order.get("fees") or ([order["fee"]] if order.get("fee") else [])
    for fee in fees:
        if fee and fee.get("currency") == "TRX":
            amount -= float(fee.get("cost") or 0)
    return amount


def _has_golden_cross(spot) -> bool:
    frame = fetch_ohlcv(SYMBOL, "1d", None, None)
    # 오늘자 마지막 봉이 아직 마감 전(진행중)인 캔들일 수 있어, 신호 판단은 전일까지 마감된
    # 봉만으로 한다 — 그래야 장중 노이즈로 하루에 여러 번 신호가 튀는 걸 막는다.
    today = now_iso()[:10]
    if str(frame.index[-1].date()) == today:
        frame = frame.iloc[:-1]
    enriched = add_ema_cross_indicators(frame).dropna(subset=["EMA9", "EMA21"])
    if len(enriched) < 2:
        return False
    ema9_prev, ema9 = enriched["EMA9"].iloc[-2], enriched["EMA9"].iloc[-1]
    ema21_prev, ema21 = enriched["EMA21"].iloc[-2], enriched["EMA21"].iloc[-1]
    return bool(ema9_prev <= ema21_prev and ema9 > ema21)


def run_cycle() -> None:
    state = load_state()
    if state.get("inception_ts") is None:
        state["inception_ts"] = now_iso()
        log_event(state, "TRX 스윙(골든크로스 진입 + 손절 -{:.0f}%) 실계좌 봇 시작".format(STOP_LOSS_PCT))

    spot = spot_client()

    try:
        ticker = spot.fetch_ticker(SYMBOL)
        current_price = ticker["last"]
    except Exception as exc:  # noqa: BLE001
        log_event(state, f"시세조회 실패 ({exc}) — 이번 사이클 건너뜀")
        save_state(state)
        return

    position = state.get("position")

    if position is not None:
        stop_price = position["entry_price"] * (1 - STOP_LOSS_PCT / 100)
        if current_price <= stop_price:
            try:
                order = spot.create_market_sell_order(SYMBOL, position["qty"])
            except Exception as exc:  # noqa: BLE001
                log_event(state, f"손절 매도 실패 ({exc}) — 다음 사이클에 재시도")
                save_state(state)
                return
            exit_price = _fill_price(order, current_price)
            proceeds = position["qty"] * exit_price
            exit_fee_usdt = proceeds * SPOT_FEE_PCT / 100
            state["cumulative_fee_usdt"] = state.get("cumulative_fee_usdt", 0.0) + exit_fee_usdt
            net_pnl = proceeds - position["notional_usdt"] - exit_fee_usdt
            state["cumulative_realized_pnl_usdt"] = state.get("cumulative_realized_pnl_usdt", 0.0) + net_pnl
            log_event(
                state,
                f"손절 매도 — 진입 {position['entry_price']:.5f} → 청산 {exit_price:.5f} "
                f"(손절선 {stop_price:.5f}), 순손익 {net_pnl:+.2f} USDT",
            )
            state["position"] = None
        else:
            unrealized = (current_price - position["entry_price"]) * position["qty"]
            log_event(
                state,
                f"보유중 — 진입 {position['entry_price']:.5f}, 현재가 {current_price:.5f} "
                f"(손절선 {stop_price:.5f}), 미실현손익 {unrealized:+.2f} USDT",
            )
    else:
        try:
            golden_cross = _has_golden_cross(spot)
        except Exception as exc:  # noqa: BLE001
            log_event(state, f"일봉 조회 실패 ({exc}) — 이번 사이클 건너뜀")
            save_state(state)
            return

        if golden_cross:
            try:
                balance = spot.fetch_balance()
                available_usdt = float((balance.get("USDT") or {}).get("free", 0.0) or 0.0)
            except Exception as exc:  # noqa: BLE001
                log_event(state, f"잔고조회 실패 ({exc}) — 이번 사이클 건너뜀")
                save_state(state)
                return

            notional_usdt = available_usdt * BALANCE_FRACTION
            if notional_usdt < MIN_NOTIONAL_USDT:
                log_event(state, f"골든크로스 발생했으나 가용잔고 부족({available_usdt:.2f} USDT) — 진입 건너뜀")
            else:
                try:
                    amount = notional_usdt / current_price
                    order = spot.create_market_buy_order(SYMBOL, amount)
                except Exception as exc:  # noqa: BLE001
                    log_event(state, f"진입 매수 실패 ({exc})")
                    save_state(state)
                    return
                entry_price = _fill_price(order, current_price)
                qty = _net_base_amount(order, amount)
                entry_fee_usdt = notional_usdt * SPOT_FEE_PCT / 100
                state["cumulative_fee_usdt"] = state.get("cumulative_fee_usdt", 0.0) + entry_fee_usdt
                state["position"] = {
                    "entry_price": entry_price,
                    "qty": qty,
                    "notional_usdt": notional_usdt,
                    "entry_fee_usdt": entry_fee_usdt,
                }
                log_event(
                    state,
                    f"골든크로스 진입 — {qty:.2f} TRX @ {entry_price:.5f} "
                    f"(노셔널 {notional_usdt:.2f} USDT, 손절선 {entry_price*(1-STOP_LOSS_PCT/100):.5f})",
                )
        else:
            log_event(state, "관망 — 골든크로스 대기중")

    total_pnl = state.get("cumulative_realized_pnl_usdt", 0.0)
    unrealized_now = 0.0
    if state.get("position"):
        unrealized_now = (current_price - state["position"]["entry_price"]) * state["position"]["qty"]
        total_pnl += unrealized_now
    state["equity_history"] = (state.get("equity_history", []) + [
        {"ts": now_iso(), "total_pnl_usdt": total_pnl}
    ])[-20000:]
    # 종목별 차트용 — 이미 조회한 현재가를 그대로 기록만 한다(추가 API 호출 없음).
    position_history = state.setdefault("position_history", {})
    trx_history = position_history.setdefault("TRX", [])
    trx_history.append({"ts": now_iso(), "price": current_price, "unrealized_pnl_usdt": unrealized_now})
    position_history["TRX"] = trx_history[-20000:]

    save_state(state)
