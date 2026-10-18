"""코인 6종목 롱숏 스윙 페이퍼봇의 상태 저장소.

trx_swing_state.py와 같은 패턴 — 이 봇은 완전 가상(paper) 모드라 API 키가 전혀 필요없다.
바이낸스 공개 시세만 조회해서 가상 포지션·손익을 추적한다(실주문 없음).
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

STATE_PATH = Path(os.environ.get("COIN_SWING6_STATE_PATH", "/app/data/coin_swing6_state.json"))

_DEFAULT_STATE = {
    "positions": {},  # base -> {side, entry_price, notional_usdt, opened_ts, unrealized_pnl_usdt}
    "trade_log": [],
    "cumulative_realized_pnl_usdt": 0.0,
    "inception_ts": None,
    "equity_history": [],
    "position_history": {},
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
