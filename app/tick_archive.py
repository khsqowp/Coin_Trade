"""틱 원본을 시간 단위 JSONL 세그먼트로 로컬에 보존한다.

짧은 메모리 버퍼는 호출부가 관리하고, 이 모듈은 연/월/일/시 파일에 append한다.
백업은 NAS 마운트에 직접 쓰지 않고 로컬 archive를 원본으로 삼는다. 한 번의 flush에서
여러 카테고리를 쓸 때 일부 파일만 성공하고 재시도되어 중복되는 일을 막기 위해,
append_batches는 파일들을 잠근 뒤 실패 시 기존 길이로 롤백한다.
"""
from __future__ import annotations

import json
import os
import fcntl
import re
from pathlib import Path
from typing import Iterable, Mapping

ARCHIVE_DIR = Path(os.environ.get("TICK_ARCHIVE_DIR", "/app/archive"))


def _hour_path(category: str, timestamp: str) -> Path:
    if not isinstance(category, str) or re.fullmatch(r"[A-Za-z0-9_-]{1,64}", category) is None:
        raise ValueError("category must contain only 1-64 ASCII letters, digits, '_' or '-'")
    if len(timestamp) < 13 or timestamp[10] != "T":
        raise ValueError(f"ts must be an ISO-8601 timestamp: {timestamp!r}")
    year, month, date = timestamp[:10].split("-")
    hour = timestamp[11:13]
    if not hour.isdigit() or int(hour) > 23:
        raise ValueError(f"invalid hour in timestamp: {timestamp!r}")
    return ARCHIVE_DIR / year / month / date / hour / f"{category}.jsonl"


def append_batch(category: str, records: Iterable[dict]) -> None:
    append_batches({category: records})


def append_batches(batches: Mapping[str, Iterable[dict]]) -> None:
    """여러 카테고리 레코드를 원자적으로 추가한다. 저장 실패는 호출자에게 전달한다."""
    grouped: dict[Path, list[bytes]] = {}
    for category, records in batches.items():
        for record in records:
            timestamp = record.get("ts")
            if not isinstance(timestamp, str):
                raise ValueError("each archive record must contain a string 'ts'")
            path = _hour_path(category, timestamp)
            grouped.setdefault(path, []).append(
                (json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
            )
    if not grouped:
        return

    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    lock_path = ARCHIVE_DIR / ".append.lock"
    lock_fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o644)
    old_sizes: dict[Path, int | None] = {}
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        for path, lines in grouped.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            old_size = path.stat().st_size if path.exists() else None
            old_sizes[path] = old_size
            fd = os.open(path, os.O_CREAT | os.O_WRONLY | os.O_APPEND, 0o644)
            with os.fdopen(fd, "ab") as stream:
                for line in lines:
                    stream.write(line)
                stream.flush()
                os.fsync(stream.fileno())
    except OSError:
        for path, old_size in reversed(list(old_sizes.items())):
            try:
                if old_size is None:
                    path.unlink(missing_ok=True)
                else:
                    with path.open("r+b") as stream:
                        stream.truncate(old_size)
                        stream.flush()
                        os.fsync(stream.fileno())
            except OSError as rollback_error:
                print(f"[틱아카이브 롤백실패] {path}: {rollback_error}", flush=True)
        raise
    finally:
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
        finally:
            os.close(lock_fd)
