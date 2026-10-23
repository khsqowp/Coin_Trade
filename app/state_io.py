"""상태 JSON 원자적 저장 공용 함수.

매 사이클 쓰는 파일이라 indent 없이 compact separators 로 쓴다(들여쓰기 제거만으로 크기가
크게 줄어 디스크/IO 부담 감소 — 파싱 결과는 동일해서 기존 로더/프런트/백엔드 JSON 파서에 영향 없음).
쓰기 실패(디스크 풀 등) 시 .tmp 를 지우고 로그를 남긴 뒤 예외는 그대로 올린다 — 기존 파일은 보존된다.
"""
from __future__ import annotations

import json
import os
from pathlib import Path


def atomic_write_json(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".tmp")
    try:
        tmp_path.write_text(json.dumps(state, separators=(",", ":"), ensure_ascii=False))
        os.replace(tmp_path, path)
    except BaseException as exc:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass
        print(f"[상태저장 실패] {path}: {exc!r} — 임시파일 제거, 기존 상태 파일 유지", flush=True)
        raise
