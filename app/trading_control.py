"""봇 수동 제어 채널 (즉시 매도 / 즉시 진입).

`api` 컨테이너가 공유 RW 볼륨의 control.json 에 명령을 쓰고, 각 로테이션 봇이 매 루프
틱마다 자기 슬롯을 읽는다. 명령은 nonce 로 식별하고, 봇은 소비한 nonce 를 자기 상태
파일에 기록해 재실행을 막는다.

의도적으로 아주 얇게 만든다 — 파일이 없거나 깨졌거나 볼륨이 안 붙어도 조용히 None 을
반환한다. 오케스트레이션이 죽어도 트레이딩 루프는 평소대로 돌아야 한다.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

CONTROL_PATH = Path(os.environ.get("TRADING_CONTROL_PATH", "/app/control/control.json"))

_VALID_CMDS = {"flatten", "enter"}


def read_command(bot: str) -> dict | None:
    """bot 슬롯의 명령을 반환하거나, 없으면 None.

    반환 형태: {"cmd": "flatten"|"enter", "nonce": str, "ts": str, "reason": str|None}
    """
    try:
        raw = CONTROL_PATH.read_text()
    except (OSError, ValueError):
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    slot = data.get(bot)
    if not isinstance(slot, dict):
        return None
    cmd = slot.get("cmd")
    nonce = slot.get("nonce")
    if cmd not in _VALID_CMDS or not isinstance(nonce, str) or not nonce:
        return None
    return {"cmd": cmd, "nonce": nonce, "ts": slot.get("ts"), "reason": slot.get("reason")}
