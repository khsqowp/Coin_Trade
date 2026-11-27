"""VOLREG-R1 포워드 가상매매 — 목표비중 리밸런싱 주문.

동결 목표비중(entry/exit 돌파로 결정된 state에 따라):
    state 1.0 (risk-on) → SPY 50% / QQQ 50% / SHY 0%
    state 0.0 (risk-off) → SPY 0% / QQQ 0% / SHY 100%

KIS 해외주식 모의투자는 지정가만 허용하므로(시장가 불가) 마켓터블 리밋 방식을 쓴다
(app/kis_overseas_order.py의 MARKETABLE_LIMIT_BUFFER와 동일 관례).

EXCD(거래소코드)는 심볼별로 KIS가 실제 어떤 코드로 라우팅하는지 이번 세션엔 모의투자 인증
문제로 확인 못 했다. 하드코딩 대신 inquire_price로 실제 응답이 오는 코드를 찾아 캐시한다
(resolve_excd). 인증 복구 후 반드시 한 번 실행해 실제 라우팅을 확인할 것.
"""
from __future__ import annotations

from app.kis_overseas_order import MARKETABLE_LIMIT_BUFFER, inquire_balance, inquire_price, place_order

ASSETS = ("SPY", "QQQ", "SHY")
TARGET_WEIGHTS = {
    1.0: {"SPY": 0.5, "QQQ": 0.5, "SHY": 0.0},
    0.0: {"SPY": 0.0, "QQQ": 0.0, "SHY": 1.0},
}
_EXCD_CANDIDATES = ("NAS", "AMS", "NYS")
_excd_cache: dict[str, str] = {}


def resolve_excd(token: str, symbol: str) -> str:
    if symbol in _excd_cache:
        return _excd_cache[symbol]
    for excd in _EXCD_CANDIDATES:
        try:
            inquire_price(token, symbol, excd)
            _excd_cache[symbol] = excd
            return excd
        except RuntimeError:
            continue
    raise RuntimeError(f"{symbol}의 거래소코드를 {_EXCD_CANDIDATES} 중에서 찾지 못함")


def current_positions(token: str, cano: str, acnt_prdt_cd: str) -> dict[str, float]:
    """심볼 -> 보유수량(소수 가능). ASSETS 외 종목은 무시(이 계좌가 다른 전략과 공유될 수 있어서)."""
    held: dict[str, float] = {}
    for excg in ("NASD", "NYSE", "AMEX"):
        body = inquire_balance(token, cano, acnt_prdt_cd, excg)
        if body.get("rt_cd") != "0":
            raise RuntimeError(f"해외잔고조회 실패({excg}): {body.get('msg_cd')} {body.get('msg1')}")
        for row in body.get("output1", []):
            symbol = row.get("ovrs_pdno")
            if symbol in ASSETS:
                held[symbol] = held.get(symbol, 0.0) + float(row.get("ovrs_cblc_qty", "0"))
    return held


def _portfolio_value_usd(token: str, positions: dict[str, float], cash_usd: float) -> float:
    total = cash_usd
    for symbol, qty in positions.items():
        if qty <= 0:
            continue
        excd = resolve_excd(token, symbol)
        total += qty * inquire_price(token, symbol, excd)
    return total


def rebalance(token: str, cano: str, acnt_prdt_cd: str, target_state: float,
             cash_usd: float) -> list[dict[str, object]]:
    """target_state(1.0/0.0)에 맞는 비중으로 전량 재배분한다. 반환값은 실행한 주문 로그."""
    target_weights = TARGET_WEIGHTS[target_state]
    positions = current_positions(token, cano, acnt_prdt_cd)
    portfolio_value = _portfolio_value_usd(token, positions, cash_usd)
    logs: list[dict[str, object]] = []

    # 먼저 비중이 줄어야 하는 자산부터 매도해 현금을 확보한 뒤, 늘어야 하는 자산을 매수한다.
    plans = []
    for symbol in ASSETS:
        excd = resolve_excd(token, symbol)
        price = inquire_price(token, symbol, excd)
        current_qty = positions.get(symbol, 0.0)
        target_value = portfolio_value * target_weights[symbol]
        target_qty = int(target_value // price)
        delta_qty = target_qty - int(current_qty)
        plans.append({"symbol": symbol, "excd": excd, "price": price, "delta_qty": delta_qty})

    for plan in sorted(plans, key=lambda p: p["delta_qty"]):  # 매도(음수)부터
        symbol, excd, price, delta_qty = plan["symbol"], plan["excd"], plan["price"], plan["delta_qty"]
        if delta_qty == 0:
            continue
        side = "sell" if delta_qty < 0 else "buy"
        qty = abs(delta_qty)
        limit_price = round(price * (1 + MARKETABLE_LIMIT_BUFFER if side == "buy"
                                      else 1 - MARKETABLE_LIMIT_BUFFER), 2)
        result = place_order(token, cano, acnt_prdt_cd, symbol, excd, side, qty, limit_price)
        logs.append({"symbol": symbol, "side": side, "qty": qty, "limit_price": limit_price,
                     "rt_cd": result.get("rt_cd"), "msg_cd": result.get("msg_cd"),
                     "msg1": result.get("msg1"), "odno": result.get("output", {}).get("ODNO")})
    return logs
