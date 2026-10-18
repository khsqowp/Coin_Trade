"""Atomic state and process locks. Readers tolerate no malformed records."""

from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator
import fcntl
import json
import os
import tempfile


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="." + path.name, dir=path.parent)
    try:
        with os.fdopen(fd, "w") as out:
            json.dump(value, out, allow_nan=False, separators=(",", ":"))
            out.flush()
            os.fsync(out.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


class StateStore:
    def __init__(self, directory: str | Path):
        self.dir = Path(directory)
        self.dir.mkdir(parents=True, exist_ok=True)

    def read(self, name: str, default: Any = None) -> Any:
        path = self.dir / name
        return json.loads(path.read_text()) if path.exists() else default

    def write(self, name: str, value: Any) -> None:
        atomic_json(self.dir / name, value)

    def append(self, name: str, value: Any) -> None:
        path = self.dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a") as out:
            out.write(json.dumps(value, allow_nan=False, separators=(",", ":")) + "\n")
            out.flush()
            os.fsync(out.fileno())

    def records(self, name: str) -> list[dict[str, Any]]:
        path = self.dir / name
        if not path.exists():
            return []
        return [
            json.loads(line) for line in path.read_text().splitlines() if line.strip()
        ]

    @contextmanager
    def lock(self, name: str = ".run.lock") -> Iterator[None]:
        with (self.dir / name).open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)

    def notes(self, generation: int) -> str:
        p = self.dir / "notes" / f"gen_{generation}.md"
        return p.read_text() if p.exists() else ""

    def write_notes(self, generation: int, text: str) -> None:
        p = self.dir / "notes" / f"gen_{generation}.md"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
