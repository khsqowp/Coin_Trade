"""VOLREG-R1 포워드 가상매매 — 목표비중 리밸런싱 (순수 레저, 실제 주문 없음).

동결 목표비중(entry/exit 돌파로 결정된 state에 따라):
    state 1.0 (risk-on)  -> SPY 50% / QQQ 50% / SHY 0%
    state 0.0 (risk-off) -> SPY 0% / QQQ 0% / SHY 100%

이건 실거래가 아니다. 토스증권 공식 시세 API(app/toss_price.py)로 받은 현재가를 기준으로
state.json 안의 가상 현금/보유수량만 갱신하는 장부 기록이고, 실제 계좌 주문·체결은 없다
(한투 KIS 모의투자 인증이 계속 막혀서 2026-11-27 사용자 승인으로 이 방식으로 전환 — "실거래
아니고 백테스트용 정보 받아오기면 진행"). 비용은 PREREG_VOLREG_R1_TEST_FREEZE.md의 왕복
12bp를 매수/매도 각 6bp로 나눠 가상 차감해 백테스트와 같은 비용 가정을 유지한다.
"""
from __future__ import annotations

from app.toss_price import get_prices

ASSETS = ("SPY", "QQQ", "SHY")
TARGET_WEIGHTS = {
    1.0: {"SPY": 0.5, "QQQ": 0.5, "SHY": 0.0},
    0.0: {"SPY": 0.0, "QQQ": 0.0, "SHY": 1.0},
}
COST_BPS_PER_LEG = 6.0  # PREREG 왕복 12bp의 절반, 매수/매도 각각


def rebalance(state: dict, target_state: float) -> list[dict[str, object]]:
    """target_state(1.0/0.0)에 맞춰 state["holdings"]/state["cash_usd"]를 가상으로 재배분한다.

    반환값은 실행한(가상) 거래 로그. state는 호출부가 load_state()/save_state()로 영속화한다.
    """
    prices = get_prices(list(ASSETS))
    weights = TARGET_WEIGHTS[target_state]
    holdings: dict[str, float] = state.setdefault("holdings", {s: 0.0 for s in ASSETS})
    cash = float(state.get("cash_usd", 0.0))
    nav = cash + sum(holdings.get(s, 0.0) * prices[s] for s in ASSETS)

    plans = []
    for symbol in ASSETS:
        price = prices[symbol]
        target_qty = int((nav * weights[symbol]) // price)
        delta_qty = target_qty - int(holdings.get(symbol, 0.0))
        plans.append({"symbol": symbol, "price": price, "delta_qty": delta_qty})

    logs: list[dict[str, object]] = []
    for plan in sorted(plans, key=lambda p: p["delta_qty"]):  # 매도(음수)부터 처리해 현금 확보
        symbol, price, delta_qty = plan["symbol"], plan["price"], plan["delta_qty"]
        if delta_qty == 0:
            continue
        notional = abs(delta_qty) * price
        cost = notional * COST_BPS_PER_LEG / 10000.0
        side = "sell" if delta_qty < 0 else "buy"
        if side == "buy":
            cash -= notional + cost
        else:
            cash += notional - cost
        holdings[symbol] = holdings.get(symbol, 0.0) + delta_qty
        logs.append({"symbol": symbol, "side": side, "qty": abs(delta_qty),
                     "price": price, "cost_usd": round(cost, 4)})

    state["holdings"] = holdings
    state["cash_usd"] = cash
    state["nav_usd"] = cash + sum(holdings.get(s, 0.0) * prices[s] for s in ASSETS)
    return logs
