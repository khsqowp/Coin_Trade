"""코인(바이낸스) 틱 웹소켓 수신 상태 저장소 — tick_state.py(KIS)와 동일 패턴."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

STATE_PATH = Path(os.environ.get("CRYPTO_TICK_STATE_PATH", "/app/data/crypto_tick_state.json"))

_DEFAULT_STATE = {
    "spot_ticks": {},     # {BASE: [{ts, price}]} — 현물 체결가 롤링버퍼(TRX, 펀딩비차익 현물레그)
    "perp_ticks": {},     # {BASE: [{ts, price}]} — 무기한선물 체결가 롤링버퍼(모멘텀 로테이션 47종목 + 펀딩비차익 선물레그)
    "funding": {},        # {BASE: [{ts, mark_price, funding_rate}]} — 실시간 예상 펀딩비(1초 간격)
    "trade_log": [],
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
