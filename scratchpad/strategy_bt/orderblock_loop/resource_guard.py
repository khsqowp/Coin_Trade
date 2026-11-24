"""Disk-space preflight for orderblock research tasks."""
from __future__ import annotations

import shutil
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


@contextmanager
def heavy_task(role: str, lock_path: Path | None = None) -> Iterator[None]:
    """Run without serialization; retain the legacy arguments for callers."""
    if shutil.disk_usage("/").free < 40 * 1024**3:
        raise RuntimeError("less than 40 GiB free on root volume")
    yield
