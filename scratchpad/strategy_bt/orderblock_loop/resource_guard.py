"""Single-heavy-run lock and resource preflight for orderblock research."""
from __future__ import annotations

import os
import shutil
import time
from datetime import datetime, timezone
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


@contextmanager
def heavy_task(role: str, lock_path: Path | None = None) -> Iterator[None]:
    """Acquire the shared research lock; never overwrite another run's lock."""
    path = lock_path or Path.home() / "CODE/trading_data/cache/.heavy.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.nice(10)
    except OSError as exc:
        raise RuntimeError(f"cannot lower research process priority: {exc}") from exc
    if shutil.disk_usage("/").free < 40 * 1024**3:
        raise RuntimeError("less than 40 GiB free on root volume")
    started = time.monotonic()
    while True:
        stamp = datetime.now(timezone.utc).isoformat()
        identity = f"{role}, {os.getpid()}, {stamp}"
        try:
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            break
        except FileExistsError:
            if time.monotonic() - started >= 3600:
                raise TimeoutError("heavy lock wait exceeded 60 minutes")
            time.sleep(300)
    try:
        os.write(descriptor, identity.encode())
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    try:
        yield
    finally:
        try:
            if path.read_text(encoding="utf-8") == identity:
                path.unlink()
        except FileNotFoundError:
            pass
