"""장중 분단위 루프 — 보유종목의 실시간 손절가만 체크하고, 전일 마감스캔이 채워둔
매매대기열(pending_entries/pending_exits)을 장시작 이후 실제 주문으로 소비한다.
쓰는 주문은 전부 시장가(place_order price=None).

예산(CAPITAL_BUDGET_KRW)은 국장 전략의 누적 실현손익만큼 늘거나 줄어든다 — entry_cost/
realized_pnl_krw를 이 파일에서 직접 추적하며, 계좌 자체(예수금)는 국장/미장 공용이므로
브로커 잔고의 매입금액합계가 아니라 이 상태파일의 자체 원장을 예산 판단 기준으로 쓴다."""
from __future__ import annotations

import datetime as dt

from app.kis_order import inquire_balance, inquire_price, place_order
from app.kr_state import log_event, now_iso, save_state
from app.kr_watchlist import (
    ACNT_PRDT_CD, CANO, CAPITAL_BUDGET_KRW, MAX_CONCURRENT_POSITIONS, MAX_POSITION_FRACTION, RISK_PER_TRADE, STOP_PCT,
)
from app.strategies import _risk_sized_fraction
from app.tick_state import load_state as load_tick_state

# 웹소켓 틱(tick_stream.py)이 이 시간 안에 갱신됐으면 REST 시세조회 대신 그 값을 쓴다 —
# tick_stream의 30초 플러시 주기를 감안한 여유치. 구독 안 된 종목/틱스트림 장애시엔
# 자동으로 REST(inquire_price)로 폴백한다.
_TICK_STALE_SECONDS = 90


def _tick_price(tick_state: dict, symbol: str) -> float | None:
    points = tick_state.get("ticks", {}).get(symbol)
    if not points:
        return None
    last = points[-1]
    try:
        ts = dt.datetime.fromisoformat(last["ts"])
    except (KeyError, ValueError):
        return None
    if (dt.datetime.now(dt.timezone.utc) - ts).total_seconds() > _TICK_STALE_SECONDS:
        return None
    try:
        return float(last["price"])
    except (KeyError, ValueError, TypeError):
        return None


def _price(token: str, symbol: str, tick_state: dict) -> float:
    tick = _tick_price(tick_state, symbol)
    return tick if tick is not None else inquire_price(token, symbol)


def _balance(token: str) -> tuple[dict[str, int], float]:
    body = inquire_balance(token, CANO, ACNT_PRDT_CD)
    if body.get("rt_cd") != "0":
        raise RuntimeError(f"잔고조회 실패: {body.get('msg_cd')} {body.get('msg1')}")
    held = {row["pdno"]: int(row["hldg_qty"]) for row in body.get("output1", []) if int(row.get("hldg_qty", "0")) > 0}
    cash = float(body["output2"][0]["dnca_tot_amt"]) if body.get("output2") else 0.0
    return held, cash


def _sell_all(token: str, state: dict, symbol: str, qty: int, price: float, reason: str) -> None:
    result = place_order(token, CANO, ACNT_PRDT_CD, symbol, "sell", qty)
    if result.get("rt_cd") == "0":
        entry_cost = state["entry_cost"].pop(symbol, qty * price)
        realized = qty * price - entry_cost
        state["realized_pnl_krw"] = state.get("realized_pnl_krw", 0.0) + realized
        log_event(state, f"[매도:{reason}] {symbol} {qty}주 @약{price:,.0f} 실현손익{realized:+,.0f} "
                          f"(누적실현손익 {state['realized_pnl_krw']:+,.0f})")
        state["stop_price"].pop(symbol, None)
    else:
        log_event(state, f"[매도실패:{reason}] {symbol}: {result.get('msg_cd')} {result.get('msg1')}")


def check_once(token: str, state: dict) -> None:
    held, _ = _balance(token)
    try:
        tick_state = load_tick_state()
    except Exception:  # noqa: BLE001
        tick_state = {}

    # 0) 상태파일이 유실된 채로 재시작된 경우(보유중인데 stop_price/entry_cost 기억이 없는 종목) 대비 —
    # 브로커 잔고가 진실 소스이므로, 빠진 종목은 현재가 기준으로 복구해 감시 공백을 막는다.
    for symbol, qty in held.items():
        if symbol not in state["stop_price"] or symbol not in state["entry_cost"]:
            try:
                price = _price(token, symbol, tick_state)
            except Exception as exc:  # noqa: BLE001
                log_event(state, f"[현재가조회실패] {symbol}: {exc}")
                continue
            state["stop_price"].setdefault(symbol, price * (1 - STOP_PCT))
            state["entry_cost"].setdefault(symbol, price * qty)
            log_event(state, f"[상태복구] {symbol}: 손절가/원가 기억 없어 현재가 기준 재설정")

    # 1) 전일 스캔이 넣어둔 청산 대기열 소비
    for symbol in list(state["pending_exits"]):
        if symbol in held:
            try:
                price = _price(token, symbol, tick_state)
            except Exception as exc:  # noqa: BLE001
                log_event(state, f"[현재가조회실패] {symbol}: {exc}")
                continue
            _sell_all(token, state, symbol, held[symbol], price, "일봉신호")
        state["pending_exits"].remove(symbol)

    # 2) 실시간 손절가 체크 (보유중인 종목만) — 이미 조회한 가격을 종목별 차트 기록에도 재사용한다.
    unrealized_pnl_krw = 0.0
    position_history = state.setdefault("position_history", {})
    for symbol, stop in list(state["stop_price"].items()):
        if symbol not in held:
            continue
        try:
            price = _price(token, symbol, tick_state)
        except Exception as exc:  # noqa: BLE001
            log_event(state, f"[현재가조회실패] {symbol}: {exc}")
            continue
        if price <= stop:
            _sell_all(token, state, symbol, held[symbol], price, f"손절@{stop:.0f}")
            continue
        symbol_unrealized = price * held[symbol] - state["entry_cost"].get(symbol, price * held[symbol])
        unrealized_pnl_krw += symbol_unrealized
        history = position_history.setdefault(symbol, [])
        history.append({"ts": now_iso(), "price": price, "unrealized_pnl_krw": symbol_unrealized})
        position_history[symbol] = history[-20000:]

    total_pnl_krw = state.get("realized_pnl_krw", 0.0) + unrealized_pnl_krw
    state["equity_history"] = (state.get("equity_history", []) + [
        {"ts": now_iso(), "total_pnl_krw": total_pnl_krw}
    ])[-20000:]

    # 3) 매도 반영된 최신 잔고/현금 + 자체 예산원장으로 신규진입 대기열 소비
    held, cash = _balance(token)
    budget = CAPITAL_BUDGET_KRW + state.get("realized_pnl_krw", 0.0)
    deployed = sum(state["entry_cost"].get(s, 0.0) for s in held)
    spendable = min(cash, max(0.0, budget - deployed))
    slots = MAX_CONCURRENT_POSITIONS - len(held)
    for symbol in list(state["pending_entries"]):
        if slots <= 0:
            break
        if symbol in held:
            state["pending_entries"].remove(symbol)
            continue
        try:
            price = _price(token, symbol, tick_state)
        except Exception as exc:  # noqa: BLE001
            log_event(state, f"[현재가조회실패] {symbol}: {exc}")
            continue
        stop = state["stop_price"].get(symbol, price * (1 - STOP_PCT))
        fraction = _risk_sized_fraction(price, stop, RISK_PER_TRADE, MAX_POSITION_FRACTION)
        qty = int((spendable * fraction) // price) if fraction else 0
        state["pending_entries"].remove(symbol)
        if qty < 1:
            log_event(state, f"[진입스킵] {symbol}: 주문가능수량 0 (예산잔여 {spendable:,.0f}/{budget:,.0f}, 가격 {price:,.0f})")
            state["stop_price"].pop(symbol, None)
            continue
        result = place_order(token, CANO, ACNT_PRDT_CD, symbol, "buy", qty)
        if result.get("rt_cd") == "0":
            cost = qty * price
            state["stop_price"][symbol] = stop
            state["entry_cost"][symbol] = cost
            log_event(state, f"[매수] {symbol} {qty}주 @약{price:,.0f} 손절가{stop:,.0f} "
                              f"(국장예산 {deployed + cost:,.0f}/{budget:,.0f} 사용)")
            spendable -= cost
            deployed += cost
            slots -= 1
        else:
            log_event(state, f"[매수실패] {symbol}: {result.get('msg_cd')} {result.get('msg1')}")
            # daily_scan에서 신호 감지 시점에 미리 넣어둔 stop_price가 남아있으면, entry_cost 없이도
            # stopPrice만 보고 "보유 포지션"으로 렌더링하는 프런트엔드 표에 체결 안 된 종목이
            # 마치 매수된 것처럼 계속 노출된다 — 매수 실패 시에도 진입스킵과 동일하게 정리한다.
            state["stop_price"].pop(symbol, None)

    save_state(state)
