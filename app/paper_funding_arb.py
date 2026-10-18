"""펀딩비 차익거래(현물 롱 + 무기한선물 숏) 모의투자 실행 로직.

funding_arb_backtest.py에서 검증된 수수료 가정(스팟 0.1%, 선물 0.05%, 편도)과 임계값을
그대로 사용한다. 이 가정은 실계좌 기준 실제 손익을 추정하기 위한 값으로, 가격 기반
손익 계산(price_pnl)만으로는 드러나지 않는 실제 수수료 비용을 별도 장부
(cumulative_fee_usdt)에서 직접 차감해 반영한다.

SOL은 백테스트에서 바이비트/바이낸스 간 펀딩비 부호가 반대로 나오는 것이 확인되어 제외한다.
"""
from __future__ import annotations

import os

from app.paper_exchange import futures_client, spot_client
from app.paper_state import load_state, log_event, now_iso, save_state

# 소액 실계좌 자본으로는 BTC 최소 주문금액(50 USDT)까지 감당하면 종목당 여유가 너무 줄어들어
# 일단 ETH/XRP/DOGE 3종목만 운용한다. 총자본이 커져서 4종목(BTC 포함) 균등분배가 다시 넉넉해지면
# 그때 BTC를 다시 추가한다.
SYMBOLS = ["ETH", "XRP", "DOGE"]
# 바이낸스 선물 최소 주문금액(USDT cost limit): ETH 20, XRP/DOGE 5.
# 총자본은 더 이상 고정값이 아니라 사이클마다 실제 잔고(스팟 보유가치+선물지갑)를 조회해 그 값의
# BALANCE_FRACTION만큼을 쓴다 — 펀딩비 수취로 잔고가 늘면 다음 신규진입 노셔널도 자동으로 커지고,
# 손실나면 줄어든다. 이미 열려있는 포지션은 재조정하지 않는다(청산 전까진 진입 당시 노셔널 유지 —
# 안 그러면 재조정할 때마다 왕복 수수료만 더 나간다). 잔고조회가 실패하면 직전 사이클 값을 그대로 쓴다.
# FUNDING_ARB_TOTAL_CAPITAL_USDT는 이제 잔고조회 자체가 실패했을 때만 쓰는 최초 기본값/폴백이다.
FALLBACK_TOTAL_CAPITAL_USDT = float(os.environ.get("FUNDING_ARB_TOTAL_CAPITAL_USDT", "90"))
BALANCE_FRACTION = float(os.environ.get("FUNDING_ARB_BALANCE_FRACTION", "0.95"))
# 신규진입 주문 실패(증거금 부족 등)가 한 번이라도 나면 다음 사이클부터 이 값으로 자동 하향한다 —
# 0.95는 완충이 얕아서 실패가 났다는 건 여유가 부족하다는 신호이기 때문. 수동 복구 전까지 유지된다.
DOWNSHIFT_BALANCE_FRACTION = 0.90
MIN_VIABLE_EQUITY_USDT = 30.0  # 잔고조회가 이상치(0에 가까운 값)를 반환하면 신규진입을 건너뛴다
SPOT_FEE_PCT = 0.1
PERP_FEE_PCT = 0.05
# 선물 지갑 증거금이 적어 레버리지 없이는 최소 주문금액조차 감당하기 어렵다. 스팟은 항상 명목가
# 전액을 실제로 매수하므로 레버리지의 영향을 받지 않고, 이 배수는 오직 선물 숏의 증거금 요구량만
# 줄인다 -- 델타중립 자체(스팟 롱 수량 == 선물 숏 수량)는 그대로 유지되므로 헤지가 깨지지 않는다.
LEVERAGE = int(os.environ.get("FUNDING_ARB_LEVERAGE", "3"))
MIN_ANNUALIZED_FUNDING_PCT_TO_ENTER = float(os.environ.get("FUNDING_ARB_MIN_ANNUALIZED_ENTRY_PCT", "5.0"))
# 신규진입 중단 스위치 — 켜두면 보유중인 포지션은 기존 로직(EXIT_IF_ANNUALIZED_FUNDING_PCT_BELOW)
# 그대로 자동 청산되지만, 청산된 자리에 새로 진입하지는 않는다. 다른 전략(TRX 스윙 등)으로
# 자금을 옮기는 동안, 판 돈이 제자리로 다시 들어가지 않게 막는 용도.
HALT_NEW_ENTRIES = os.environ.get("FUNDING_ARB_HALT_NEW_ENTRIES", "false").lower() == "true"
EXIT_IF_ANNUALIZED_FUNDING_PCT_BELOW = 0.0
FUNDING_SETTLEMENTS_PER_YEAR = 3 * 365  # 8시간마다 정산
# 델타중립(현물 롱 + 선물 숏) 전략이라 정상적인 변동성은 매우 낮아야 한다 — 두 자릿수대 손실은
# 시세 변동이 아니라 버그, 헤지 깨짐, 체결 슬리피지 같은 구조적 문제를 의미할 가능성이 높다.
# 사용자가 제안한 10%보다 조금 더 보수적으로 8%를 한도로 잡아, 문제를 더 일찍 잡아낸다.
MAX_DRAWDOWN_PCT_OF_CAPITAL = 8.0


def _spot_symbol(base: str) -> str:
    return f"{base}/USDT"


def _perp_symbol(base: str) -> str:
    return f"{base}/USDT:USDT"


def _annualized_funding_pct(funding_rate: float) -> float:
    return funding_rate * 100 * FUNDING_SETTLEMENTS_PER_YEAR


def _credit_settled_funding(state: dict, fut, base: str, perp_symbol: str, position: dict) -> float:
    """바이낸스 실제 정산 내역(fetch_funding_history)에서 직전 처리 이후 새로 발생한 건만
    골라 누적한다. 8시간마다 한 번만 실제로 정산되므로, 사이클 주기(초 단위)와 무관하게
    정확한 금액만 반영된다."""
    last_ts = state.setdefault("funding_last_ts_ms", {}).get(base)
    try:
        since = (last_ts + 1) if last_ts else None
        entries = fut.fetch_funding_history(perp_symbol, since=since, limit=50)
    except Exception as exc:  # noqa: BLE001
        log_event(state, f"{base}: 실정산 내역 조회 실패 ({exc}) — 이번 사이클은 건너뜀")
        return 0.0

    new_entries = [e for e in entries if last_ts is None or e["timestamp"] > last_ts]
    if not new_entries:
        return 0.0

    credited = sum(e["amount"] for e in new_entries)
    state["funding_last_ts_ms"][base] = max(e["timestamp"] for e in new_entries)
    state["cumulative_funding_usdt"] = state.get("cumulative_funding_usdt", 0.0) + credited
    position["accrued_funding_usdt"] = position.get("accrued_funding_usdt", 0.0) + credited
    return credited


def run_cycle() -> None:
    state = load_state()
    if state.get("inception_ts") is None:
        state["inception_ts"] = now_iso()
        log_event(state, f"모의투자 시작 — 총 자본은 매 사이클 실제 잔고 기준으로 동적 산정됩니다 ({len(SYMBOLS)}종목)")

    if state.get("trading_halted"):
        return

    if HALT_NEW_ENTRIES and not state.get("halt_new_entries_logged"):
        log_event(state, "⚠ 신규진입 중단 모드 — 보유중인 포지션은 기존 청산조건대로 자동 매도되지만, 이후 재진입은 하지 않습니다(자금 이관 진행중).")
        state["halt_new_entries_logged"] = True

    spot = spot_client()
    fut = futures_client()

    try:
        total_equity_usdt = _total_equity_usdt(spot, fut)
    except Exception as exc:
        total_equity_usdt = state.get("total_capital_usdt") or FALLBACK_TOTAL_CAPITAL_USDT
        log_event(state, f"잔고조회 실패 ({exc}) — 이번 사이클은 직전 총자본 {total_equity_usdt:.2f} USDT 유지")

    if total_equity_usdt < MIN_VIABLE_EQUITY_USDT:
        log_event(state, f"잔고조회 결과가 비정상적으로 작음({total_equity_usdt:.2f} USDT < {MIN_VIABLE_EQUITY_USDT}) — 신규진입 건너뛰고 직전값 유지")
        total_equity_usdt = state.get("total_capital_usdt") or FALLBACK_TOTAL_CAPITAL_USDT
        notional_per_symbol_usdt = 0.0  # 이번 사이클은 신규진입 금지, 보유중 포지션 관리는 계속함
    else:
        effective_balance_fraction = state.get("balance_fraction_override") or BALANCE_FRACTION
        notional_per_symbol_usdt = effective_balance_fraction * total_equity_usdt / len(SYMBOLS)

    for base in SYMBOLS:
        spot_symbol = _spot_symbol(base)
        perp_symbol = _perp_symbol(base)
        position = state["positions"].get(base)

        try:
            funding = fut.fetch_funding_rate(perp_symbol)
            rate = funding.get("fundingRate")
        except Exception as exc:
            log_event(state, f"{base}: 펀딩비 조회 실패 ({exc}) — 이번 사이클 건너뜀")
            continue

        if rate is None:
            log_event(state, f"{base}: 펀딩비 없음 — 건너뜀")
            continue

        annualized = _annualized_funding_pct(rate)

        if position is None:
            if HALT_NEW_ENTRIES:
                continue
            if notional_per_symbol_usdt <= 0:
                continue
            if annualized >= MIN_ANNUALIZED_FUNDING_PCT_TO_ENTER:
                _open_position(state, spot, fut, base, spot_symbol, perp_symbol, rate, annualized, notional_per_symbol_usdt)
            else:
                log_event(state, f"{base}: 관망 (연환산 펀딩 {annualized:.2f}% < 진입기준 {MIN_ANNUALIZED_FUNDING_PCT_TO_ENTER}%)")
        else:
            # fetch_funding_rate()가 주는 rate는 "다음 정산 예정 요율"이라 사이클마다(현재 60초)
            # 새로 수취한 것처럼 누적하면 실제 정산(8시간마다)보다 수백 배 부풀려진다 — 반드시
            # 바이낸스의 실제 정산 내역(fetch_funding_history)에서 직전 처리 이후 새로 발생한
            # 건만 골라 누적해야 한다. rate/annualized는 진입기준 판단(연환산 추정치)에만 쓴다.
            credited = _credit_settled_funding(state, fut, base, perp_symbol, position)
            log_event(
                state,
                f"{base}: 보유중, 현재 요율 {rate * 100:.4f}% (연환산 {annualized:.2f}%) "
                f"이번 사이클 실정산 수취 {credited:+.4f} USDT, 누적수취 {position['accrued_funding_usdt']:.4f} USDT",
            )

            if annualized < EXIT_IF_ANNUALIZED_FUNDING_PCT_BELOW:
                _close_position(state, spot, fut, base, spot_symbol, perp_symbol)

    # 델타중립(현물 롱 + 선물 숏) 가정이 실제로 지켜지고 있는지 매 사이클 마크투마켓으로 확인한다 —
    # 스팟·선물은 서로 다른 실제 오더북이라 베이시스가 벌어지거나 체결 슬리피지가 있으면 이 값이
    # 0에서 벗어나고, 그만큼이 곧 펀딩비만으로는 설명되지 않는 실제 가격 위험이다.
    unrealized_price_pnl_usdt = _unrealized_price_pnl_usdt(state, spot, fut)
    state["unrealized_price_pnl_usdt"] = unrealized_price_pnl_usdt

    state["total_capital_usdt"] = total_equity_usdt
    total_pnl_usdt = (
        state.get("cumulative_funding_usdt", 0.0)
        + state.get("cumulative_price_pnl_usdt", 0.0)
        + unrealized_price_pnl_usdt
        - state.get("cumulative_fee_usdt", 0.0)
    )
    state["total_pnl_usdt"] = total_pnl_usdt

    # 손실한도도 현재 실제잔고 기준 — 자본이 늘면 한도도 같이 늘고, 줄면 더 보수적으로 빨리 멈춘다.
    drawdown_pct = -total_pnl_usdt / total_equity_usdt * 100
    if drawdown_pct >= MAX_DRAWDOWN_PCT_OF_CAPITAL:
        log_event(
            state,
            f"⚠ 손실 한도 도달 (누적손익 {total_pnl_usdt:+.2f} USDT, 자본 대비 {drawdown_pct:.2f}% ≥ 한도 "
            f"{MAX_DRAWDOWN_PCT_OF_CAPITAL:.0f}%) — 전 포지션을 청산하고 거래를 중지합니다. 재개하려면 상태 파일의 "
            f"trading_halted를 수동으로 초기화해야 합니다.",
        )
        for base in list(state["positions"].keys()):
            _close_position(state, spot, fut, base, _spot_symbol(base), _perp_symbol(base))
        state["trading_halted"] = True
        state["unrealized_price_pnl_usdt"] = 0.0  # 전량 청산했으니 더 이상 미실현 포지션이 없음
        total_pnl_usdt = (
            state.get("cumulative_funding_usdt", 0.0)
            + state.get("cumulative_price_pnl_usdt", 0.0)
            - state.get("cumulative_fee_usdt", 0.0)
        )
        state["total_pnl_usdt"] = total_pnl_usdt

    state.setdefault("equity_history", []).append({"ts": now_iso(), "total_pnl_usdt": total_pnl_usdt})
    state["equity_history"] = state["equity_history"][-20000:]  # 10분 주기 기준 약 4~5개월치 보관

    save_state(state)


def _fill_price(order: dict, fallback: float) -> float:
    """시장가 주문의 실제 체결가를 우선 쓰고, 거래소 응답에 없으면 직전 조회한 티커가로 대체한다."""
    price = order.get("average") or order.get("price")
    return float(price) if price else fallback


def _net_base_amount(order: dict, requested_amount: float, base: str) -> float:
    """스팟 매수 주문 체결 후 실제로 보유하게 되는 기초자산 수량을 계산한다.

    바이낸스는 기본적으로 매수 수수료를 매수한 자산 자체에서 징수한다(예: BTC 매수 시 BTC로 차감).
    테스트넷은 수수료가 0이라 요청 수량과 실제 보유 수량이 항상 같았지만, 실계좌는 그렇지 않다 —
    이 차이를 무시하면 선물 숏이 실제 보유량보다 많아져 헤지가 어긋나고, 청산 시 스팟 매도 주문이
    실제 잔고를 초과해 거절될 수 있다.
    """
    filled = order.get("filled")
    amount = float(filled) if filled else requested_amount
    fees = order.get("fees") or ([order["fee"]] if order.get("fee") else [])
    for fee in fees:
        if fee and fee.get("currency") == base:
            amount -= float(fee.get("cost") or 0)
    return amount


def _mark_price(client, symbol: str) -> float:
    return client.fetch_ticker(symbol)["last"]


def _total_equity_usdt(spot, fut) -> float:
    """스팟(USDT+보유코인 평가액)과 선물지갑(증거금+미실현손익 포함 총액)을 합친 실제 총자본.
    신규진입 노셔널 산정과 손실한도 계산 모두 이 값을 기준으로 한다."""
    spot_balance = spot.fetch_balance()
    spot_usdt = float((spot_balance.get("USDT") or {}).get("total", 0.0) or 0.0)
    spot_crypto_value = 0.0
    for base in SYMBOLS:
        qty = float((spot_balance.get(base) or {}).get("total", 0.0) or 0.0)
        if qty:
            spot_crypto_value += qty * _mark_price(spot, _spot_symbol(base))
    futures_balance = fut.fetch_balance()
    futures_usdt = float((futures_balance.get("USDT") or {}).get("total", 0.0) or 0.0)
    return spot_usdt + spot_crypto_value + futures_usdt


def _unrealized_price_pnl_usdt(state, spot, fut) -> float:
    total = 0.0
    symbol_history = state.setdefault("position_history", {})
    for base, position in state["positions"].items():
        entry_spot = position.get("entry_spot_price", position.get("entry_price"))
        entry_perp = position.get("entry_perp_price", position.get("entry_price"))
        if entry_spot is None or entry_perp is None:
            continue
        try:
            current_spot = _mark_price(spot, _spot_symbol(base))
            current_perp = _mark_price(fut, _perp_symbol(base))
        except Exception:
            continue  # 이번 사이클 시세 조회 실패 — 다음 사이클에 다시 계산되므로 그냥 건너뜀
        amount = position["amount"]
        position_pnl = (current_spot - entry_spot) * amount + (entry_perp - current_perp) * amount
        position["unrealized_price_pnl_usdt"] = position_pnl
        total += position_pnl
        # 종목별 차트용 — 이미 조회한 가격을 그대로 기록만 한다(추가 API 호출 없음).
        base_history = symbol_history.setdefault(base, [])
        base_history.append({"ts": now_iso(), "price": current_spot, "unrealized_pnl_usdt": position_pnl, "accrued_funding_usdt": position.get("accrued_funding_usdt", 0.0)})
        symbol_history[base] = base_history[-20000:]
    return total


def _downshift_balance_fraction(state: dict, reason: str) -> None:
    current = state.get("balance_fraction_override") or BALANCE_FRACTION
    if current <= DOWNSHIFT_BALANCE_FRACTION:
        return
    state["balance_fraction_override"] = DOWNSHIFT_BALANCE_FRACTION
    log_event(
        state,
        f"[자동조정] 신규진입 실패({reason})로 balance_fraction을 {DOWNSHIFT_BALANCE_FRACTION}로 하향 — "
        f"복구하려면 상태파일의 balance_fraction_override를 수동으로 지우세요.",
    )


def _open_position(state, spot, fut, base, spot_symbol, perp_symbol, rate, annualized, notional_usdt: float) -> None:
    try:
        fut.set_leverage(LEVERAGE, perp_symbol)
    except Exception as exc:
        log_event(state, f"{base}: 진입 실패 (레버리지 설정 단계) ({exc})")
        _downshift_balance_fraction(state, "레버리지 설정 실패")
        return

    try:
        ticker = spot.fetch_ticker(spot_symbol)
        price = ticker["last"]
        amount = notional_usdt / price
        spot_order = spot.create_market_buy_order(spot_symbol, amount)
    except Exception as exc:
        log_event(state, f"{base}: 진입 실패 (스팟 매수 단계) ({exc})")
        _downshift_balance_fraction(state, "스팟 매수 실패")
        return

    # 실제로 보유하게 되는 수량(hedge_amount)은 요청 수량(amount)과 다를 수 있다 — 선물 숏은
    # 반드시 실제 보유량과 맞춰야 델타중립이 깨지지 않고, 이후 청산 시 스팟 매도도 이 수량을
    # 넘기지 않아야 잔고부족으로 거절되지 않는다.
    hedge_amount = _net_base_amount(spot_order, amount, base)

    # 스팟은 이미 체결됐는데 선물 숏 진입이 실패하면, 헤지 안 된 스팟 롱만 거래소에 남는다 -- 이걸
    # 그냥 두면 델타중립 전략의 핵심 전제(가격변동 리스크 제거)가 깨진 채로 시스템은 그 포지션의
    # 존재조차 모르게 된다. 즉시 되팔아 원상복구하고, 왕복 수수료(모의)를 장부에 반영한다.
    try:
        perp_order = fut.create_market_sell_order(perp_symbol, hedge_amount)
    except Exception as exc:
        try:
            spot.create_market_sell_order(spot_symbol, hedge_amount)
        except Exception as unwind_exc:
            log_event(
                state,
                f"{base}: 선물 숏 진입 실패 ({exc}) 후 스팟 되팔기도 실패 ({unwind_exc}) — "
                f"헤지 안 된 스팟 포지션이 거래소에 남아있을 수 있습니다. 수동 확인 필요.",
            )
            _downshift_balance_fraction(state, "선물 숏 진입 실패 + 되팔기 실패")
            return
        unwind_fee_usdt = notional_usdt * SPOT_FEE_PCT / 100 * 2
        state["cumulative_fee_usdt"] = state.get("cumulative_fee_usdt", 0.0) + unwind_fee_usdt
        log_event(
            state,
            f"{base}: 선물 숏 진입 실패 ({exc}) — 스팟을 즉시 되팔아 원상복구했습니다. "
            f"왕복수수료(모의) {unwind_fee_usdt:.2f} USDT",
        )
        _downshift_balance_fraction(state, "선물 숏 진입 실패")
        return

    # 현물 롱 + 선물 숏이 실제로는 서로 다른 오더북이라, 체결가가 같다고 가정하지 않고 각 다리의
    # 실제 체결가를 따로 기록한다 — 이 차이(베이시스)가 나중에 청산 시 가격손익 계산의 기준이 된다.
    entry_spot_price = _fill_price(spot_order, price)
    entry_perp_price = _fill_price(perp_order, price)

    entry_fee_usdt = notional_usdt * (SPOT_FEE_PCT + PERP_FEE_PCT) / 100
    state["cumulative_fee_usdt"] = state.get("cumulative_fee_usdt", 0.0) + entry_fee_usdt
    state["positions"][base] = {
        "notional_usdt": notional_usdt,
        "entry_price": entry_spot_price,
        "entry_spot_price": entry_spot_price,
        "entry_perp_price": entry_perp_price,
        "amount": hedge_amount,
        "entry_fee_usdt": entry_fee_usdt,
        "accrued_funding_usdt": 0.0,
    }
    basis_note = "" if entry_spot_price == entry_perp_price else f" (베이시스 {entry_perp_price - entry_spot_price:+.4f})"
    log_event(
        state,
        f"{base}: 진입 (연환산 펀딩 {annualized:.2f}%, 최근 펀딩 {rate * 100:.4f}%) "
        f"현물매수+선물매도 {hedge_amount:.6f} @ 현물 {entry_spot_price:.4f}/선물 {entry_perp_price:.4f}{basis_note}, "
        f"진입수수료(모의) {entry_fee_usdt:.2f} USDT",
    )


def _close_position(state, spot, fut, base, spot_symbol, perp_symbol) -> None:
    position = state["positions"].get(base)
    if position is None:
        return
    amount = position["amount"]
    # 레거시 포지션(이 기능 이전에 진입한 것) 호환 — 다리별 체결가가 없으면 기존 단일 entry_price를
    # 두 다리 모두의 진입가로 취급해, 최소한 청산 시 이 함수가 죽지 않고 가격손익을 0으로 처리한다.
    entry_spot_price = position.get("entry_spot_price", position.get("entry_price"))
    entry_perp_price = position.get("entry_perp_price", position.get("entry_price"))
    try:
        spot_order = spot.create_market_sell_order(spot_symbol, amount)
    except Exception as exc:
        log_event(state, f"{base}: 청산 실패 (스팟 매도 단계) ({exc})")
        return

    # 스팟은 이미 팔렸는데 선물 숏 청산(매수)이 실패하면, 헤지 없는 선물 숏만 남는다 -- 원래
    # 포지션(스팟 롱+선물 숏)으로 되돌리기 위해 스팟을 즉시 재매수한다. 되돌렸으므로 포지션은
    # 청산되지 않은 것으로 취급하고(state에서 지우지 않음), 왕복 수수료(모의)만 반영한다.
    try:
        perp_order = fut.create_market_buy_order(perp_symbol, amount)
    except Exception as exc:
        try:
            spot.create_market_buy_order(spot_symbol, amount)
        except Exception as unwind_exc:
            log_event(
                state,
                f"{base}: 선물 숏 청산 실패 ({exc}) 후 스팟 재매수도 실패 ({unwind_exc}) — "
                f"헤지 안 된 선물 숏 포지션이 거래소에 남아있을 수 있습니다. 수동 확인 필요.",
            )
            return
        unwind_fee_usdt = position["notional_usdt"] * SPOT_FEE_PCT / 100 * 2
        state["cumulative_fee_usdt"] = state.get("cumulative_fee_usdt", 0.0) + unwind_fee_usdt
        log_event(
            state,
            f"{base}: 선물 숏 청산 실패 ({exc}) — 스팟을 즉시 재매수해 원래 포지션으로 복구했습니다. "
            f"왕복수수료(모의) {unwind_fee_usdt:.2f} USDT (청산은 취소됨)",
        )
        return

    fallback_price = entry_spot_price if entry_spot_price is not None else 0.0
    exit_spot_price = _fill_price(spot_order, fallback_price)
    exit_perp_price = _fill_price(perp_order, entry_perp_price if entry_perp_price is not None else fallback_price)

    price_pnl_usdt = 0.0
    if entry_spot_price is not None and entry_perp_price is not None:
        price_pnl_usdt = (exit_spot_price - entry_spot_price) * amount + (entry_perp_price - exit_perp_price) * amount

    exit_fee_usdt = position["notional_usdt"] * (SPOT_FEE_PCT + PERP_FEE_PCT) / 100
    state["cumulative_fee_usdt"] = state.get("cumulative_fee_usdt", 0.0) + exit_fee_usdt
    state["cumulative_price_pnl_usdt"] = state.get("cumulative_price_pnl_usdt", 0.0) + price_pnl_usdt
    net_pnl = position["accrued_funding_usdt"] + price_pnl_usdt - position["entry_fee_usdt"] - exit_fee_usdt
    state["realized_pnl_usdt"] = state.get("realized_pnl_usdt", 0.0) + net_pnl
    log_event(
        state,
        f"{base}: 청산 — 누적펀딩수취 {position['accrued_funding_usdt']:.2f} USDT, "
        f"가격손익(베이시스/슬리피지) {price_pnl_usdt:+.2f} USDT, "
        f"진입+청산수수료(모의) {position['entry_fee_usdt'] + exit_fee_usdt:.2f} USDT, "
        f"순손익 {net_pnl:+.2f} USDT",
    )
    del state["positions"][base]
