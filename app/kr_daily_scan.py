"""장마감후 1회 — 워치리스트 45종목의 일봉으로 EmaCrossStrategy 신호를 재계산해
신규진입/청산 대기열(pending_entries/pending_exits)만 갱신한다. 주문은 여기서 내지 않는다
(장마감 직후엔 KIS가 주문을 거부함 — 실측 확인된 40580000 오류). 실제 매수/매도는
kr_intraday_risk.py가 다음 장시작에 대기열을 소비하며 낸다.
"""
from __future__ import annotations

import datetime as dt

import pandas as pd

from app.kis_auth import issue_token
from app.kis_data import fetch_ohlcv_kis
from app.kis_order import inquire_balance
from app.kr_state import load_state, log_event, save_state
from app.kr_watchlist import ACNT_PRDT_CD, CANO, MIN_USABLE_BARS, STOCK_UNIVERSE, STOP_PCT
from app.more_indicators import add_ema_cross_indicators


def _held_symbols(token: str) -> set[str]:
    body = inquire_balance(token, CANO, ACNT_PRDT_CD)
    if body.get("rt_cd") != "0":
        raise RuntimeError(f"잔고조회 실패: {body.get('msg_cd')} {body.get('msg1')}")
    return {row["pdno"] for row in body.get("output1", []) if int(row.get("hldg_qty", "0")) > 0}


def _signal(frame: pd.DataFrame) -> dict | None:
    if frame.empty or len(frame) < MIN_USABLE_BARS:
        return None
    enriched = add_ema_cross_indicators(frame).dropna()
    if len(enriched) < 2:
        return None
    ema9, ema9_prev = enriched["EMA9"].iloc[-1], enriched["EMA9"].iloc[-2]
    ema21, ema21_prev = enriched["EMA21"].iloc[-1], enriched["EMA21"].iloc[-2]
    close = enriched["Close"].iloc[-1]
    sma200 = enriched["SMA200"].iloc[-1]
    crossed_up = ema9_prev <= ema21_prev and ema9 > ema21
    crossed_down = ema9_prev >= ema21_prev and ema9 < ema21
    return {
        "crossed_up": bool(crossed_up),
        "crossed_down": bool(crossed_down),
        "above_sma200": bool(close > sma200),
        "close": float(close),
        "last_date": str(enriched.index[-1].date()),
        # EMA9/21이 얼마나 근접했는지(교차 임박도) — 작을수록 곧 골든/데드크로스날 가능성 높음.
        # tick_stream 웹소켓 동시구독 한도 초과시 우선순위로 쓴다(신호 임박 종목부터 실시간 틱 확보).
        "ema_gap_pct": abs(ema9 - ema21) / abs(ema21) if ema21 else float("inf"),
    }


def run_once(token: str | None = None) -> None:
    state = load_state()
    today = dt.datetime.now(dt.timezone.utc).astimezone(dt.timezone(dt.timedelta(hours=9))).date().isoformat()
    if state.get("last_scan_date") == today:
        print(f"오늘({today}) 이미 스캔 완료, 건너뜀")
        return

    if token is None:
        token = issue_token()
    held = _held_symbols(token)
    since = (dt.date.today() - dt.timedelta(days=380)).isoformat()

    new_entries: list[str] = []
    new_exits: list[str] = []
    rank_candidates: list[tuple[str, float]] = []
    for symbol, name in STOCK_UNIVERSE:
        try:
            frame = fetch_ohlcv_kis(symbol, token, since)
        except Exception as exc:  # noqa: BLE001
            log_event(state, f"[스캔] {name}({symbol}) 시세조회 실패, 건너뜀: {exc}")
            continue
        sig = _signal(frame)
        if sig is None:
            continue
        rank_candidates.append((symbol, sig["ema_gap_pct"]))

        if symbol in held:
            if sig["crossed_down"] or not sig["above_sma200"]:
                if symbol not in state["pending_exits"]:
                    new_exits.append(symbol)
        else:
            if sig["crossed_up"] and sig["above_sma200"]:
                stop = sig["close"] * (1 - STOP_PCT)
                state["stop_price"][symbol] = stop
                if symbol not in state["pending_entries"]:
                    new_entries.append(symbol)

    state["pending_entries"] = list(dict.fromkeys(state["pending_entries"] + new_entries))
    state["pending_exits"] = list(dict.fromkeys(state["pending_exits"] + new_exits))
    state["last_scan_date"] = today
    # 종목코드가 숫자라 대시보드에서 못 알아보므로, 감시종목 전체의 코드->한글명을 매 스캔마다
    # 새로 채워넣는다(정적 워치리스트라 매일 다시 써도 저렴하고, 누락 없이 항상 최신 유지).
    state["symbol_names"] = {symbol: name for symbol, name in STOCK_UNIVERSE}
    rank_candidates.sort(key=lambda pair: pair[1])
    state["tick_rank"] = [symbol for symbol, _ in rank_candidates]

    if new_entries:
        log_event(state, f"[스캔] 신규진입 대기: {new_entries}")
    if new_exits:
        log_event(state, f"[스캔] 청산 대기: {new_exits}")
    if not new_entries and not new_exits:
        log_event(state, "[스캔] 신규 신호 없음")

    save_state(state)


if __name__ == "__main__":
    run_once()
