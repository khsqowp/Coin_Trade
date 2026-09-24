"""코인 6종목 롱숏 스윙 페이퍼봇 — 실주문 없음, 실계좌 리스크 전혀 없음.

사용자가 설명한 아이디어를 그대로 규칙화했다: "6개 코인을 계속 지켜보다가 방향이 확실한 애가
있으면(롱이든 숏이든) 1개 사서 들고 있다가, 오르면(또는 숏이면 내려가면) 팔고 또 다른 신호
기다리는" 로테이션 — 종목당 슬롯 1개씩, 최대 6개 동시 보유(사용자 확정).

- 신호(진입): EMA9/21 크로스 + SMA200 추세필터. kr/us_daily_scan.py·trx_swing_trade.py와
  동일한 검증된 조합을 그대로 재사용 — 롱은 골든크로스+SMA200 위, 숏은 데드크로스+SMA200
  아래(반대로 대칭 적용, 여기서 처음 씀 — 기존 봇들은 전부 롱온리 현물이라 숏 조건이 없었음).
- 청산: 고정 익절/손절 %(사용자 확정, 기본 +5%/-3%) — 트레일링 없음, TRX 손절(-12%)보다
  타이트한 이유는 TRX와 달리 방향을 맞추면 바로 익절하고 다음 신호로 넘어가는 회전형 전략이라
  느슨한 손절을 오래 들고 있을 이유가 없어서.
- 자본: 가상자본을 6등분해서 슬롯당 고정 배분(레버리지 없음, 1x) — 페이퍼라 단순하게.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import ccxt

from app.coin_swing6_state import load_state, log_event, now_iso, save_state
from app.futures_data import fetch_perp_ohlcv
from app.more_indicators import add_ema_cross_indicators

SYMBOLS = ["BTC", "ETH", "SOL", "XRP", "DOGE", "BNB"]

TP_PCT = float(os.environ.get("COIN_SWING6_TP_PCT", "5.0"))
SL_PCT = float(os.environ.get("COIN_SWING6_SL_PCT", "3.0"))
START_CAPITAL_USDT = float(os.environ.get("COIN_SWING6_START_CAPITAL_USDT", "1000"))
SLOT_FRACTION = 1.0 / len(SYMBOLS)
LOOKBACK_DAYS = 200 + 30  # SMA200 워밍업 + EMA 안정화 여유


def _perp_symbol(base: str) -> str:
    return f"{base}/USDT:USDT"


def _fetch_prices(exchange: ccxt.binance) -> dict[str, float]:
    tickers = exchange.fetch_tickers([_perp_symbol(b) for b in SYMBOLS])
    prices = {}
    for base in SYMBOLS:
        last = (tickers.get(_perp_symbol(base)) or {}).get("last")
        if last:
            prices[base] = float(last)
    return prices


def _signal(base: str) -> dict | None:
    since_iso = (datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)).isoformat()
    frame = fetch_perp_ohlcv(_perp_symbol(base), "1d", since_iso, None)
    if frame.empty:
        return None
    # 오늘자 마지막 봉이 아직 마감 전(진행중)일 수 있어, 신호 판단은 전일까지 마감된 봉만으로
    # 한다 — trx_swing_trade.py와 동일한 이유(장중 노이즈로 하루에 여러 번 신호가 튀는 것 방지).
    today = now_iso()[:10]
    if str(frame.index[-1].date()) == today:
        frame = frame.iloc[:-1]
    enriched = add_ema_cross_indicators(frame).dropna(subset=["EMA9", "EMA21", "SMA200"])
    if len(enriched) < 2:
        return None
    ema9_prev, ema9 = enriched["EMA9"].iloc[-2], enriched["EMA9"].iloc[-1]
    ema21_prev, ema21 = enriched["EMA21"].iloc[-2], enriched["EMA21"].iloc[-1]
    close = enriched["Close"].iloc[-1]
    sma200 = enriched["SMA200"].iloc[-1]
    return {
        "crossed_up": bool(ema9_prev <= ema21_prev and ema9 > ema21),
        "crossed_down": bool(ema9_prev >= ema21_prev and ema9 < ema21),
        "above_sma200": bool(close > sma200),
        "below_sma200": bool(close < sma200),
    }


def _close_position(state: dict, base: str, pos: dict, price: float, tag: str) -> None:
    entry = pos["entry_price"]
    side_sign = 1.0 if pos["side"] == "long" else -1.0
    pnl = pos["notional_usdt"] * side_sign * (price / entry - 1)
    state["cumulative_realized_pnl_usdt"] = state.get("cumulative_realized_pnl_usdt", 0.0) + pnl
    log_event(
        state,
        f"{base} {tag} — {pos['side']} 진입 {entry:.6g} → 청산 {price:.6g} "
        f"({(side_sign * (price / entry - 1) * 100):+.2f}%), 손익 {pnl:+.2f} USDT",
    )
    del state["positions"][base]


def run_cycle() -> None:
    state = load_state()
    if state.get("inception_ts") is None:
        state["inception_ts"] = now_iso()
        log_event(
            state,
            f"코인 6종목 롱숏 스윙 페이퍼봇 시작 — {', '.join(SYMBOLS)}, "
            f"익절+{TP_PCT:.0f}%/손절-{SL_PCT:.0f}%, 가상자본 {START_CAPITAL_USDT:,.0f} USDT "
            f"(종목당 {START_CAPITAL_USDT * SLOT_FRACTION:,.0f} USDT)",
        )

    exchange = ccxt.binance({"enableRateLimit": True, "options": {"defaultType": "future"}})
    try:
        prices = _fetch_prices(exchange)
    except Exception as exc:  # noqa: BLE001
        log_event(state, f"시세조회 실패 ({exc}) — 이번 사이클 건너뜀")
        save_state(state)
        return

    positions = state.setdefault("positions", {})

    for base in SYMBOLS:
        price = prices.get(base)
        if price is None:
            continue

        pos = positions.get(base)
        if pos is not None:
            entry = pos["entry_price"]
            side_sign = 1.0 if pos["side"] == "long" else -1.0
            change_pct = side_sign * (price / entry - 1) * 100
            if change_pct >= TP_PCT:
                _close_position(state, base, pos, price, "익절")
            elif change_pct <= -SL_PCT:
                _close_position(state, base, pos, price, "손절")
            else:
                pos["unrealized_pnl_usdt"] = pos["notional_usdt"] * side_sign * (price / entry - 1)
            continue

        # 빈 슬롯 — 신호 확인(일봉 조회라 상대적으로 비쌈, 채워진 슬롯은 건너뛰어 절약)
        try:
            sig = _signal(base)
        except Exception as exc:  # noqa: BLE001
            log_event(state, f"{base}: 일봉 조회 실패 ({exc})")
            continue
        if not sig:
            continue

        notional = START_CAPITAL_USDT * SLOT_FRACTION
        if sig["crossed_up"] and sig["above_sma200"]:
            positions[base] = {
                "side": "long", "entry_price": price, "notional_usdt": notional,
                "opened_ts": now_iso(), "unrealized_pnl_usdt": 0.0,
            }
            log_event(state, f"{base} 롱 진입 — {price:.6g} (EMA9/21 골든크로스 + SMA200 위)")
        elif sig["crossed_down"] and sig["below_sma200"]:
            positions[base] = {
                "side": "short", "entry_price": price, "notional_usdt": notional,
                "opened_ts": now_iso(), "unrealized_pnl_usdt": 0.0,
            }
            log_event(state, f"{base} 숏 진입 — {price:.6g} (EMA9/21 데드크로스 + SMA200 아래)")

    unrealized_total = sum(p.get("unrealized_pnl_usdt", 0.0) for p in positions.values())
    equity = START_CAPITAL_USDT + state.get("cumulative_realized_pnl_usdt", 0.0) + unrealized_total
    state["equity_usdt"] = equity
    state["unrealized_pnl_usdt"] = unrealized_total
    state["equity_history"] = (state.get("equity_history", []) + [
        {"ts": now_iso(), "total_pnl_usdt": equity - START_CAPITAL_USDT}
    ])[-2000:]

    # 종목별 차트용 — 이미 조회한 가격을 그대로 기록만 한다(추가 API 호출 없음).
    symbol_history = state.setdefault("position_history", {})
    for base, price in prices.items():
        history = symbol_history.setdefault(base, [])
        pos = positions.get(base)
        history.append({
            "ts": now_iso(), "price": price,
            "unrealized_pnl_usdt": pos.get("unrealized_pnl_usdt", 0.0) if pos else 0.0,
        })
        symbol_history[base] = history[-2000:]

    save_state(state)
