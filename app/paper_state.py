"""JSON 파일 기반 모의투자 상태 저장소 — 컨테이너가 재시작돼도 포지션/누적 손익을 유지한다."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

STATE_PATH = Path(os.environ.get("PAPER_STATE_PATH", "/app/data/funding_arb_state.json"))

_DEFAULT_STATE = {
    "positions": {},
    "trade_log": [],
    "cumulative_funding_usdt": 0.0,
    "cumulative_fee_usdt": 0.0,
    "cumulative_price_pnl_usdt": 0.0,
    "unrealized_price_pnl_usdt": 0.0,
    "realized_pnl_usdt": 0.0,
    "inception_ts": None,
    "equity_history": [],
    "trading_halted": False,
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_state() -> dict:
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text())
    return json.loads(json.dumps(_DEFAULT_STATE))


def save_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    # 디스크 풀 등으로 쓰기가 중간에 끊겨도 기존 파일이 0바이트로 손상되지 않도록,
    # 임시 파일에 먼저 쓰고 완료된 뒤에만 원자적으로 교체한다.
    tmp_path = STATE_PATH.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(state, indent=2, ensure_ascii=False))
    os.replace(tmp_path, STATE_PATH)


def log_event(state: dict, message: str) -> None:
    entry = {"ts": now_iso(), "message": message}
    state.setdefault("trade_log", []).append(entry)
    # 로그가 무한정 커지지 않도록 최근 2000건만 보관
    state["trade_log"] = state["trade_log"][-2000:]
    print(f"[{entry['ts']}] {message}", flush=True)
