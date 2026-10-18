"""국내주식 스윙 자동매매 상태 저장소 — 실제 보유/현금은 KIS 잔고조회가 진실 소스이고,
여기엔 전략 판단에 필요한 부가정보(스탑가, 매매대기 큐)만 저장한다."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

STATE_PATH = Path(os.environ.get("KR_SWING_STATE_PATH", "/app/data/kr_swing_state.json"))

_DEFAULT_STATE = {
    "stop_price": {},        # {symbol: stop_price} — 보유중 종목의 실시간 손절가
    "entry_cost": {},        # {symbol: 매수원가(KRW)} — 실현손익 계산 + 예산 산정용
    "symbol_names": {},      # {symbol: 한글 종목명} — 대시보드에 숫자코드 대신 표시용, kr_daily_scan에서 채움
    "tick_rank": [],         # 워치리스트 전체를 EMA9/21 근접도로 정렬한 순위 — kr_daily_scan이 매일 갱신,
                              # tick_stream이 웹소켓 동시구독 한도 초과시 우선순위로 사용
    "realized_pnl_krw": 0.0,  # 누적 실현손익 — 예산이 이 값만큼 늘거나 줄어든다(kr_watchlist.CAPITAL_BUDGET_KRW 참고)
    "pending_entries": [],   # 장마감후 스캔에서 신규진입 신호 뜬 종목, 다음 장시작에 매수
    "pending_exits": [],     # 장마감후 스캔에서 청산 신호 뜬 종목, 다음 장시작에 매도
    "last_scan_date": None,  # "YYYY-MM-DD" — 일일 스캔 중복실행 방지
    "trade_log": [],
    "equity_history": [],    # [{ts, total_pnl_krw}] — 대시보드 기간별(일/주/월/전체) 손익 차트용
    "position_history": {},  # {symbol: [{ts, price, unrealized_pnl_krw}]} — 종목별 차트용
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_state() -> dict:
    if not STATE_PATH.exists():
        return json.loads(json.dumps(_DEFAULT_STATE))
    state = json.loads(STATE_PATH.read_text())
    # 이전 버전 상태파일에 없던 키(예: entry_cost 추가 전)를 기본값으로 채워 하위호환 유지
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
