"""코인 롱숏 스윙 페이퍼봇 — 실주문 없음, 실계좌 리스크 전혀 없음.

2026-09-25 재설계(사용자 명시 요구): 고정 6종목이 아니라 momentum_rotation_loop.py와
같은 전체 유니버스(45종목)를 매 사이클(요청 단위)마다 통째로 재계산한다. 그 중 최대
MAX_SLOTS(6)개까지만 동시 보유 — "가장 수익 확률이 높은" 종목을 추세강도(SMA200
이격도) 점수로 순위 매겨 빈 슬롯에 채운다.

- 신호(진입/청산 공통): EMA9/21 크로스 + SMA200 추세필터. kr/us_daily_scan.py·
  trx_swing_trade.py·momentum_rotation_loop.py와 동일한 검증된 조합.
  롱 진입 = 골든크로스 + SMA200 위, 숏 진입 = 데드크로스 + SMA200 아래.
- 점수(순위) = |종가 - SMA200| / SMA200 * 100 — 추세가 강할수록(눌림 없이 확실히 위/
  아래로 벌어져 있을수록) 점수가 높다. 여러 종목이 동시에 신호를 내면 점수 높은
  순으로 빈 슬롯을 채운다.
- 보유 포지션 청산 조건 두 가지(둘 중 하나만 충족해도 청산):
  1) 고정 익절/손절 %(기본 +5%/-3%, 환경변수로 조정 가능) — 기존 그대로.
  2) "확실한 손실 예측" = 보유 방향과 반대되는 크로스가 방금 발생(추세 반전 확정,
     단순히 SMA200 아래/위로 걸치는 정도가 아니라 EMA9/21이 실제로 반대로 꺾인
     경우만 — 잔파동에 휘둘리지 않게). 반전 청산된 슬롯은 같은 사이클에서 바로
     그 시점 최고점수 후보로 재진입(갈아타기)을 시도한다. 반전 신호가 없으면
     슬롯은 그대로 유지(익절/손절 걸릴 때까지 회전하지 않음).
- 자본: 가상자본을 MAX_SLOTS 등분해서 슬롯당 고정 배분(레버리지 없음, 1x).
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import ccxt

from app.coin_swing6_state import load_state, log_event, now_iso, save_state
from app.futures_data import fetch_perp_ohlcv
from app.momentum_rotation_loop import UNIVERSE, _should_sample_equity_history
from app.more_indicators import add_ema_cross_indicators

MAX_SLOTS = int(os.environ.get("COIN_SWING6_MAX_SLOTS", "6"))

TP_PCT = float(os.environ.get("COIN_SWING6_TP_PCT", "5.0"))
SL_PCT = float(os.environ.get("COIN_SWING6_SL_PCT", "3.0"))
START_CAPITAL_USDT = float(os.environ.get("COIN_SWING6_START_CAPITAL_USDT", "1000"))
SLOT_FRACTION = 1.0 / MAX_SLOTS
LOOKBACK_DAYS = 200 + 30  # SMA200 워밍업 + EMA 안정화 여유
# equity_history 표본 개수 상한 — 사이클(기본 120초)마다 무조건 찍으면 2000개 상한으론
# 최대 2.8일치밖에 못 담아 momentum_rotation_loop.py와 같은 "일간/주간/전체 다 똑같다" 문제가
# 그대로 재현된다(2026-09-26 발견, 배포 전에 미리 막음). momentum_rotation_loop.py의
# EQUITY_HISTORY_SAMPLE_SECONDS(5분) 표본 게이트를 그대로 재사용해 사이클 주기와 분리하고,
# 상한도 5분 간격 기준 90일치(25920개)로 맞춘다.
EQUITY_HISTORY_MAX_POINTS = int(os.environ.get("COIN_SWING6_EQUITY_HISTORY_MAX_POINTS", "25920"))


def _perp_symbol(base: str) -> str:
    return f"{base}/USDT:USDT"


def _fetch_prices(exchange: ccxt.binance) -> dict[str, float]:
    # 45종목을 개별 fetch_ticker로 부르면 비효율 — momentum_rotation_loop.py와 같은 이유로
    # 한 번에 받는다.
    tickers = exchange.fetch_tickers([_perp_symbol(b) for b in UNIVERSE])
    prices = {}
    for base in UNIVERSE:
        last = (tickers.get(_perp_symbol(base)) or {}).get("last")
        if last:
            prices[base] = float(last)
    return prices


def _signal(base: str, exchange: ccxt.binance) -> dict | None:
    since_iso = (datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)).isoformat()
    frame = fetch_perp_ohlcv(_perp_symbol(base), "1d", since_iso, None, exchange=exchange)
    if frame.empty:
        return None
    # 오늘자 마지막 봉이 아직 마감 전(진행중)일 수 있어, 신호 판단은 전일까지 마감된 봉만으로
    # 한다(장중 노이즈로 하루에 여러 번 신호가 튀는 것 방지).
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
    score = abs(close - sma200) / sma200 * 100 if sma200 else 0.0
    return {
        "crossed_up": bool(ema9_prev <= ema21_prev and ema9 > ema21),
        "crossed_down": bool(ema9_prev >= ema21_prev and ema9 < ema21),
        "above_sma200": bool(close > sma200),
        "below_sma200": bool(close < sma200),
        "score": float(score),
    }


def _close_position(state: dict, base: str, pos: dict, price: float, tag: str) -> float:
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
    return pnl


def _open_position(state: dict, base: str, side: str, price: float, score: float, rank_note: str) -> None:
    notional = START_CAPITAL_USDT * SLOT_FRACTION
    state["positions"][base] = {
        "side": side, "entry_price": price, "notional_usdt": notional,
        "opened_ts": now_iso(), "unrealized_pnl_usdt": 0.0,
    }
    label = "골든크로스 + SMA200 위" if side == "long" else "데드크로스 + SMA200 아래"
    log_event(state, f"{base} {'롱' if side == 'long' else '숏'} 진입 — {price:.6g} ({label}, 점수 {score:.2f}{rank_note})")


def run_cycle() -> None:
    state = load_state()
    if state.get("inception_ts") is None:
        state["inception_ts"] = now_iso()
        log_event(
            state,
            f"코인 롱숏 스윙 페이퍼봇 시작 — 유니버스 {len(UNIVERSE)}종목 중 최대 {MAX_SLOTS}슬롯, "
            f"익절+{TP_PCT:.0f}%/손절-{SL_PCT:.0f}%/추세반전 갈아타기, 가상자본 {START_CAPITAL_USDT:,.0f} USDT "
            f"(슬롯당 {START_CAPITAL_USDT * SLOT_FRACTION:,.0f} USDT)",
        )

    exchange = ccxt.binance({"enableRateLimit": True, "options": {"defaultType": "future"}})
    try:
        prices = _fetch_prices(exchange)
    except Exception as exc:  # noqa: BLE001
        log_event(state, f"시세조회 실패 ({exc}) — 이번 사이클 건너뜀")
        save_state(state)
        return

    positions = state.setdefault("positions", {})

    # 1) 유니버스 전체 재계산 — 보유 포지션의 반전 청산 판단과 빈 슬롯 후보 순위 산정에
    #    똑같이 쓰인다("매 사이클마다 전체 재계산", 부분적 스캔 아님). exchange 인스턴스를
    #    45종목 전부 재사용 — 종목마다 새로 만들면 매번 load_markets()(exchangeInfo)가 다시
    #    걸려서 사이클당 요청 수가 배로 늘고, 그 exchangeInfo 호출이 간헐적으로 실패해서
    #    멀쩡한 종목까지 "일봉 조회 실패"로 스킵되는 원인이었다(2026-09-26 실로그로 확인).
    signals: dict[str, dict] = {}
    for base in UNIVERSE:
        if base not in prices:
            continue
        try:
            sig = _signal(base, exchange)
        except Exception as exc:  # noqa: BLE001
            log_event(state, f"{base}: 일봉 조회 실패 ({exc})")
            continue
        if sig is not None:
            signals[base] = sig

    # 2) 보유 포지션 — 익절/손절 우선, 그다음 반전 확정 시 청산(같은 사이클에 갈아타기).
    reopened_slots = 0
    for base in list(positions.keys()):
        price = prices.get(base)
        pos = positions[base]
        if price is None:
            continue
        entry = pos["entry_price"]
        side_sign = 1.0 if pos["side"] == "long" else -1.0
        change_pct = side_sign * (price / entry - 1) * 100
        if change_pct >= TP_PCT:
            _close_position(state, base, pos, price, "익절")
            reopened_slots += 1
            continue
        if change_pct <= -SL_PCT:
            _close_position(state, base, pos, price, "손절")
            reopened_slots += 1
            continue
        sig = signals.get(base)
        reversed_against = sig is not None and (
            (pos["side"] == "long" and sig["crossed_down"]) or (pos["side"] == "short" and sig["crossed_up"])
        )
        if reversed_against:
            _close_position(state, base, pos, price, "추세반전 갈아타기")
            reopened_slots += 1
            continue
        pos["unrealized_pnl_usdt"] = pos["notional_usdt"] * side_sign * (price / entry - 1)

    # 3) 빈 슬롯 채우기 — 보유중이 아닌 종목 중 진입신호가 뜬 것들을 점수 내림차순 정렬해
    #    상위부터 채운다. TP/SL/반전으로 방금 비운 슬롯도 이 사이클에 바로 재진입 대상.
    empty_slots = MAX_SLOTS - len(positions)
    if empty_slots > 0:
        candidates = []
        for base, sig in signals.items():
            if base in positions:
                continue
            if sig["crossed_up"] and sig["above_sma200"]:
                candidates.append((sig["score"], base, "long"))
            elif sig["crossed_down"] and sig["below_sma200"]:
                candidates.append((sig["score"], base, "short"))
        candidates.sort(key=lambda c: -c[0])
        chosen = candidates[:empty_slots]
        for rank, (score, base, side) in enumerate(chosen, start=1):
            rank_note = f", 후보 {len(candidates)}개 중 {rank}위"
            _open_position(state, base, side, prices[base], score, rank_note)

    unrealized_total = sum(p.get("unrealized_pnl_usdt", 0.0) for p in positions.values())
    equity = START_CAPITAL_USDT + state.get("cumulative_realized_pnl_usdt", 0.0) + unrealized_total
    state["equity_usdt"] = equity
    state["unrealized_pnl_usdt"] = unrealized_total
    sample_now = _should_sample_equity_history(state)
    if sample_now:
        state["equity_history"] = (state.get("equity_history", []) + [
            {"ts": now_iso(), "total_pnl_usdt": equity - START_CAPITAL_USDT}
        ])[-EQUITY_HISTORY_MAX_POINTS:]

    # 종목별 차트용 — 지금 보유중인 종목만 남긴다(45종목 전체를 다 남기면 상태파일이
    # 불필요하게 커짐). 이미 조회한 가격을 그대로 기록만 한다(추가 API 호출 없음). equity_history와
    # 같은 표본 간격을 써서 서로 다른 기간 필터끼리 어긋나지 않게 맞춘다.
    symbol_history = state.setdefault("position_history", {})
    if sample_now:
        for base, pos in positions.items():
            price = prices.get(base)
            if price is None:
                continue
            history = symbol_history.setdefault(base, [])
            history.append({"ts": now_iso(), "price": price, "unrealized_pnl_usdt": pos.get("unrealized_pnl_usdt", 0.0)})
            symbol_history[base] = history[-EQUITY_HISTORY_MAX_POINTS:]
    # 더 이상 안 들고 있는 종목의 옛 기록은 정리(무한정 쌓이는 걸 방지).
    for base in list(symbol_history.keys()):
        if base not in positions:
            del symbol_history[base]

    save_state(state)
