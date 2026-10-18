"""TRX 스윙(골든크로스 진입 + 느슨한 손절선) 실계좌 봇의 상태 저장소.

trx_buy_hold_wide_stop_backtest.py로 검증한 규칙을 그대로 실거래로 옮긴 것 — 임시(temporary)
전략이라는 점을 명시: 펀딩비 차익거래(paper_funding_arb.py)의 신규진입을 막아 자연 청산시킨
자금을 이 계좌에서 그대로 이어받아 쓴다(별도 이체 로직 없음, 같은 실계좌의 여유 USDT를 그때그때
조회해서 사용).
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

STATE_PATH = Path(os.environ.get("TRX_SWING_STATE_PATH", "/app/data/trx_swing_state.json"))

_DEFAULT_STATE = {
    "position": None,  # {entry_price, qty, notional_usdt, entry_fee_usdt} | None
    "trade_log": [],
    "cumulative_realized_pnl_usdt": 0.0,
    "cumulative_fee_usdt": 0.0,
    "inception_ts": None,
    "equity_history": [],
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_state() -> dict:
    if not STATE_PATH.exists():
        return json.loads(json.dumps(_DEFAULT_STATE))
    state = json.loads(STATE_PATH.read_text())
    for key, default in _DEFAULT_STATE.items():
        state.setdefault(key, json.loads(json.dumps(default)))
    return state


def save_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = STATE_PATH.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(state, indent=2, ensure_ascii=False))
    os.replace(tmp_path, STATE_PATH)


def log_event(state: dict, message: str) -> None:
    entry = {"ts": now_iso(), "message": message}
    state.setdefault("trade_log", []).append(entry)
    state["trade_log"] = state["trade_log"][-2000:]
    print(f"[{entry['ts']}] {message}", flush=True)
