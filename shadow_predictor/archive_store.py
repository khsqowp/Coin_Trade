"""Durable local shadow-event spool and verified NAS archiver."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
DEFAULT_DB = HERE / "runtime" / "shadow_archive.sqlite3"
DEFAULT_NAS_ROOT = Path("/Volumes/HDD2TB/Trade")
DEFAULT_VOLUME_MOUNT = Path("/Volumes/HDD2TB")
AGENT_LABEL = "com.cointrade.shadow-archive"
LOCAL_ARCHIVE_DIR = Path.home() / "Library" / "Application Support" / "CoinTradeShadowArchive"


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _digest_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _verify_gzip(path: Path, expected_digest: str, expected_count: int) -> None:
    digest = hashlib.sha256()
    count = 0
    with gzip.open(path, "rb") as handle:
        for line in handle:
            if not line.endswith(b"\n"):
                raise IOError(f"archive contains an incomplete JSONL line: {path}")
            json.loads(line)
            digest.update(line)
            count += 1
    if digest.hexdigest() != expected_digest or count != expected_count:
        raise IOError(f"archive verification failed: {path}")


class ShadowArchiveStore:
    """SQLite spool. Rows are removed only after the published NAS gzip is read back."""

    def __init__(self, db_path: Path = DEFAULT_DB):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS events (
                event_id TEXT PRIMARY KEY,
                event_date TEXT NOT NULL,
                payload TEXT NOT NULL,
                recorded_at TEXT NOT NULL
            )""")
            db.execute("CREATE INDEX IF NOT EXISTS events_by_date ON events(event_date, event_id)")
            db.execute("""CREATE TABLE IF NOT EXISTS archived_batches (
                relative_path TEXT PRIMARY KEY,
                sha256 TEXT NOT NULL,
                row_count INTEGER NOT NULL,
                archived_at TEXT NOT NULL
            )""")
        self.db_path.chmod(0o600)

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.db_path, timeout=30)
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA synchronous=FULL")
        return db

    def record_output(self, output: dict[str, Any]) -> int:
        """Idempotently persist all currently available forecasts, scores and snapshots."""
        now = datetime.now(timezone.utc)
        event_date = now.strftime("%Y-%m-%d")
        rows: list[tuple[str, str, str, str]] = []

        def add(event_id: str, kind: str, payload: dict[str, Any]) -> None:
            envelope = {"kind": kind, "recorded_at": now.isoformat(), "data": payload}
            rows.append((event_id, event_date, _canonical_json(envelope), now.isoformat()))

        for item in output.get("pending", []):
            key = f"{item.get('symbol')}:{item.get('horizon')}:{item.get('origin_minute')}"
            add(f"forecast:{key}", "forecast", item)
        for item in output.get("scores", []):
            key = f"{item.get('symbol')}:{item.get('horizon')}:{item.get('origin_minute')}:{item.get('target_minute')}"
            add(f"score:{key}", "score", item)
        for item in output.get("expired", []):
            key = f"{item.get('symbol')}:{item.get('horizon')}:{item.get('origin_minute')}:{item.get('target_minute')}"
            add(f"expired:{key}", "expired", item)
        for symbol, item in output.get("latest_forecasts", {}).items():
            key = f"{symbol}:{item.get('origin_minute')}"
            add(f"latest_forecast:{key}", "latest_forecast", {"symbol": symbol, **item})
        snapshot = output.get("strategy_snapshot")
        if isinstance(snapshot, dict):
            source_stamp = str(output.get("source_updated_at", "unknown"))
            snapshot_hash = hashlib.sha256(_canonical_json(snapshot).encode()).hexdigest()
            add(f"strategy_snapshot:{source_stamp}:{snapshot_hash}", "strategy_snapshot", {
                "source_updated_at": source_stamp, "strategies": snapshot,
            })
        if not rows:
            return 0
        with self._connect() as db:
            before = db.total_changes
            db.executemany(
                "INSERT OR IGNORE INTO events(event_id,event_date,payload,recorded_at) VALUES(?,?,?,?)",
                rows,
            )
            return db.total_changes - before

    @staticmethod
    def _assert_nas_mounted(nas_root: Path, volume_mount: Path) -> None:
        nas_root = nas_root.resolve()
        volume_mount = volume_mount.resolve()
        try:
            nas_root.relative_to(volume_mount)
        except ValueError as exc:
            raise RuntimeError(f"NAS destination is outside the expected mount: {nas_root}") from exc
        if not os.path.ismount(volume_mount):
            raise RuntimeError(f"NAS volume is not mounted at {volume_mount}; local spool retained")
        if not nas_root.is_dir():
            raise RuntimeError(f"NAS Trade directory is unavailable: {nas_root}; local spool retained")

    def flush_closed_days(
        self,
        nas_root: Path = DEFAULT_NAS_ROOT,
        volume_mount: Path = DEFAULT_VOLUME_MOUNT,
        *,
        require_mount: bool = True,
    ) -> dict[str, int]:
        """Export UTC-closed days; keep today's rows and all rows on any error."""
        nas_root = Path(nas_root)
        if require_mount:
            self._assert_nas_mounted(nas_root, Path(volume_mount))
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        with self._connect() as db:
            days = [row[0] for row in db.execute(
                "SELECT DISTINCT event_date FROM events WHERE event_date < ? ORDER BY event_date", (today,)
            )]

        exported = deleted = 0
        for day in days:
            with self._connect() as db:
                rows = db.execute(
                    "SELECT event_id,payload FROM events WHERE event_date=? ORDER BY event_id", (day,)
                ).fetchall()
            if not rows:
                continue
            raw = b"".join((payload + "\n").encode("utf-8") for _, payload in rows)
            raw_digest = hashlib.sha256(raw).hexdigest()
            year, month, date = day.split("-")
            relative = Path("shadow-predictor") / year / month / date / f"events-{raw_digest}.jsonl.gz"
            target_dir = nas_root / relative.parent
            target_dir.mkdir(parents=True, exist_ok=True)
            target = nas_root / relative

            if target.exists():
                _verify_gzip(target, raw_digest, len(rows))
            else:
                fd, temporary_name = tempfile.mkstemp(prefix=".shadow-events-", suffix=".tmp", dir=target_dir)
                temporary = Path(temporary_name)
                try:
                    with os.fdopen(fd, "wb") as raw_file:
                        with gzip.GzipFile(filename="", mode="wb", fileobj=raw_file, mtime=0) as compressed:
                            compressed.write(raw)
                        raw_file.flush()
                        os.fsync(raw_file.fileno())
                    _verify_gzip(temporary, raw_digest, len(rows))
                    os.replace(temporary, target)
                    _verify_gzip(target, raw_digest, len(rows))
                finally:
                    if temporary.exists():
                        temporary.unlink()

            # The NAS object is independently readable and verified before local deletion.
            with self._connect() as db:
                db.execute("BEGIN IMMEDIATE")
                db.execute(
                    "INSERT OR REPLACE INTO archived_batches(relative_path,sha256,row_count,archived_at) VALUES(?,?,?,?)",
                    (str(relative), raw_digest, len(rows), datetime.now(timezone.utc).isoformat()),
                )
                db.executemany("DELETE FROM events WHERE event_id=?", ((event_id,) for event_id, _ in rows))
            exported += 1
            deleted += len(rows)
        return {"days_exported": exported, "events_deleted_after_verification": deleted}


def install_agent() -> Path:
    """Install a per-user launchd retry every 15 minutes, without relying on repo location literals."""
    agent_dir = Path.home() / "Library" / "LaunchAgents"
    agent_dir.mkdir(parents=True, exist_ok=True)
    LOCAL_ARCHIVE_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    LOCAL_ARCHIVE_DIR.chmod(0o700)
    worker_script = LOCAL_ARCHIVE_DIR / "archive_store.py"
    shutil.copy2(Path(__file__).resolve(), worker_script)
    worker_script.chmod(0o600)
    plist_path = agent_dir / f"{AGENT_LABEL}.plist"
    plist = {
        "Label": AGENT_LABEL,
        "ProgramArguments": [sys.executable, str(worker_script), "--db",
                             str(LOCAL_ARCHIVE_DIR / "shadow_archive.sqlite3"), "--flush"],
        "WorkingDirectory": str(LOCAL_ARCHIVE_DIR),
        "StartInterval": 900,
        "RunAtLoad": True,
        "StandardOutPath": str(LOCAL_ARCHIVE_DIR / "shadow_archive_worker.log"),
        "StandardErrorPath": str(LOCAL_ARCHIVE_DIR / "shadow_archive_worker.log"),
    }
    import plistlib
    with plist_path.open("wb") as handle:
        plistlib.dump(plist, handle, sort_keys=True)
    uid = os.getuid()
    subprocess.run(["launchctl", "bootout", f"gui/{uid}/{AGENT_LABEL}"], check=False, capture_output=True)
    subprocess.run(["launchctl", "bootstrap", f"gui/{uid}", str(plist_path)], check=True)
    subprocess.run(["launchctl", "kickstart", "-k", f"gui/{uid}/{AGENT_LABEL}"], check=False)
    return plist_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--nas-root", type=Path, default=DEFAULT_NAS_ROOT)
    parser.add_argument("--volume-mount", type=Path, default=DEFAULT_VOLUME_MOUNT)
    parser.add_argument("--flush", action="store_true", help="export verified UTC-closed days")
    parser.add_argument("--install-agent", action="store_true", help="install and start the macOS retry agent")
    args = parser.parse_args()
    if args.install_agent:
        print(install_agent())
        return 0
    if not args.flush:
        parser.error("choose --flush or --install-agent")
    store = ShadowArchiveStore(args.db)
    try:
        print(json.dumps(store.flush_closed_days(args.nas_root, args.volume_mount), sort_keys=True))
    except Exception as exc:
        print(f"archive retained locally: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
