#!/usr/bin/env python3
"""Safely gzip and verify closed hourly tick archives on a mounted NAS."""
import argparse
import contextlib
import errno
import fcntl
import gzip
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import threading
import time
import zlib
from datetime import datetime, timedelta, timezone

LOG = logging.getLogger("archive_to_nas")
CHUNK = 1024 * 1024
DEFAULT_MOUNT = Path("/Volumes/HDD2TB")
DEFAULT_DEST = DEFAULT_MOUNT / "Trade/tick-archive"
DEFAULT_SOURCE = Path(__file__).resolve().parents[2] / "trading-tick-archive"
DEFAULT_STATE = Path.home() / "Library/Application Support/ochestration-archive"
MOUNT_CHECK = None
MOUNT_RUNNER = None
MOUNT_SLEEP = time.sleep
DEFAULT_HARD_KILL_GRACE_SECONDS = 300


class BackupError(RuntimeError):
    pass


def is_real_mount(path):
    return os.path.ismount(path)


def _utc(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _json_append(path, obj):
    with path.open("a+b") as out:
        out.seek(0, os.SEEK_END)
        if out.tell():
            out.seek(-1, os.SEEK_END)
            if out.read(1) != b"\n":
                out.seek(0, os.SEEK_END)
                out.write(b"\n")
        out.seek(0, os.SEEK_END)
        out.write((json.dumps(obj, sort_keys=True, separators=(",", ":")) + "\n").encode())
        out.flush()
        os.fsync(out.fileno())


def _records(path):
    if not path.exists():
        return []
    result = []
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            try:
                item = json.loads(line)
                if isinstance(item, dict):
                    result.append(item)
            except (ValueError, TypeError):
                LOG.error("Ignoring malformed record in %s", path)
    return result


def _file_hash(path, deadline=None, throttle=0, heartbeat=None):
    digest, size = hashlib.sha256(), 0
    with path.open("rb") as stream:
        while True:
            if deadline is not None and time.monotonic() >= deadline:
                raise TimeoutError("max-minutes reached during file read")
            block = stream.read(CHUNK)
            if not block:
                break
            if heartbeat:
                heartbeat()
            digest.update(block)
            size += len(block)
            if throttle:
                time.sleep(len(block) / (throttle * 1024 * 1024))
    return size, digest.hexdigest()


def _stat_identity(st):
    return (st.st_size, st.st_mtime_ns, st.st_ctime_ns, st.st_ino)


def _hash_open_file(stream, deadline=None, throttle=0, heartbeat=None):
    digest, size = hashlib.sha256(), 0
    while True:
        if deadline is not None and time.monotonic() >= deadline:
            raise TimeoutError("max-minutes reached during file read")
        block = stream.read(CHUNK)
        if not block: break
        if heartbeat: heartbeat()
        digest.update(block); size += len(block)
        if throttle: time.sleep(len(block) / (throttle * 1024 * 1024))
    return size, digest.hexdigest()


def _hour_from_path(source, root):
    rel = source.relative_to(root)
    if len(rel.parts) < 5:
        raise ValueError("expected YYYY/MM/DD/HH/<file>.jsonl")
    return datetime(*(int(x) for x in rel.parts[:4]), tzinfo=timezone.utc)


def _scan(root, now, close_margin_hours=6):
    found = []
    for path in root.glob("[0-9][0-9][0-9][0-9]/[0-9][0-9]/[0-9][0-9]/[0-9][0-9]/*.jsonl"):
        if path.is_symlink() or any(parent.is_symlink() for parent in path.parents if parent != root.parent):
            continue
        try:
            hour, stat = _hour_from_path(path, root), os.stat(path, follow_symlinks=False)
        except (OSError, ValueError):
            continue
        # A UTC day is eligible only after it ended and its configured close margin elapsed.
        day_end = hour.replace(hour=0) + timedelta(days=1)
        if day_end + timedelta(hours=close_margin_hours) <= now and datetime.fromtimestamp(stat.st_mtime, timezone.utc) < now:
            found.append((hour, path, stat))
    return sorted(found, key=lambda item: (item[0], str(item[1])))


def _manifest(dest, rel):
    return dest / rel.parent.parent / "manifest.jsonl"


def _latest_upload(records, rel):
    matches = [r for r in records if r.get("type", "upload") == "upload" and r.get("path") == rel.as_posix()]
    return matches[-1] if matches else None


def _verified(records, rel, upload):
    if not upload.get("upload_id"):
        return None
    return next((r for r in reversed(records) if r.get("type") == "verified" and
                 r.get("path") == rel.as_posix() and r.get("sha256") == upload.get("sha256") and
                 r.get("upload_id") == upload.get("upload_id")), None)


def _epoch(value, fallback):
    try:
        return datetime.fromisoformat(value).timestamp()
    except (TypeError, ValueError, OverflowError):
        return fallback


def _eligible_after_backoff(src, failure_dir, key_fn, now_epoch):
    try:
        return float(json.loads((failure_dir / key_fn(src)).read_text()).get("retry_after", 0)) <= now_epoch
    except (OSError, ValueError, TypeError, AttributeError):
        return True


def _atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(str(path) + ".tmp")
    with tmp.open("w", encoding="utf-8") as stream:
        json.dump(value, stream)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(tmp, path)
    fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _mount_check(args, root, dest):
    mount = Path(args.mount).resolve()
    dest = Path(dest).resolve()
    try:
        if MOUNT_CHECK is not None:
            valid = MOUNT_CHECK(mount, dest, root)
        else:
            valid = (is_real_mount(mount) and dest != mount and mount in dest.parents and
                     dest.is_dir() and os.stat(dest).st_dev == os.stat(mount).st_dev != os.stat(root).st_dev)
        if not valid:
            raise BackupError("NAS mount/destination identity check failed")
    except OSError as exc:
        raise BackupError("NAS mount unavailable: %s" % exc)


def _preflight(args):
    root, mount, dest = Path(args.source).resolve(), Path(args.mount).resolve(), Path(args.dest).resolve()
    _mount_check(args, root, dest)
    if args.dry_run or args.report:
        return
    probe = dest / (".archive_to_nas_probe_%d_%d" % (os.getpid(), time.monotonic_ns()))
    created = False
    try:
        with probe.open("xb") as f:
            created = True
            f.write(b"probe")
            f.flush()
            os.fsync(f.fileno())
    except OSError as exc:
        raise BackupError("destination not writable: %s" % exc)
    finally:
        if created:
            with contextlib.suppress(FileNotFoundError):
                probe.unlink()


def _ensure_mounted(args, root, dest):
    try:
        _mount_check(args, root, dest)
        return True
    except BackupError:
        pass
    configured_mount = Path(args.mount)
    expected_mount = Path("/Volumes") / args.nas_share
    if args.no_auto_mount or (MOUNT_RUNNER is None and configured_mount != expected_mount):
        return False
    if any(value in args.nas_user for value in (":", "@", "/")) or any(
            value in host for host in (args.nas_server, args.nas_fallback_host)
            for value in ("@", "/", ":")):
        LOG.error("invalid NAS mount identity; refusing to construct server URL")
        return False
    for host in (args.nas_server, args.nas_fallback_host):
        argv = ["open", "-g", "-j", "smb://%s@%s/%s" % (args.nas_user, host, args.nas_share)]
        try:
            if MOUNT_RUNNER is None:
                result = subprocess.run(argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                        stderr=subprocess.DEVNULL, timeout=args.mount_timeout)
                returncode = result.returncode
            else:
                returncode = MOUNT_RUNNER(argv, timeout=args.mount_timeout)
            LOG.info("mount request for %s returned %s", host, returncode)
        except (subprocess.TimeoutExpired, OSError) as exc:
            LOG.warning("mount request for %s failed: %s", host, type(exc).__name__)
        deadline = time.monotonic() + max(0, args.mount_wait)
        while True:
            try:
                _mount_check(args, root, dest)
                return True
            except BackupError:
                if time.monotonic() >= deadline:
                    break
                MOUNT_SLEEP(min(2, max(0, deadline - time.monotonic())))
    return False


def _copy_gzip(src, gz_path, deadline, throttle, heartbeat=None):
    part = Path(str(gz_path) + ".part")
    if not part.parent.is_dir():
        raise BackupError("destination hour directory does not exist: %s" % part.parent)
    original_hash, gz_hash = hashlib.sha256(), hashlib.sha256()
    size = gz_size = 0
    before = src.stat()
    try:
        with src.open("rb") as raw, part.open("wb") as target:
            with gzip.GzipFile(fileobj=target, mode="wb", compresslevel=6, mtime=0) as zipped:
                while True:
                    if time.monotonic() >= deadline:
                        raise TimeoutError("max-minutes reached during upload")
                    block = raw.read(CHUNK)
                    if not block:
                        break
                    if heartbeat:
                        heartbeat()
                    original_hash.update(block); size += len(block); zipped.write(block)
                    if throttle:
                        time.sleep(len(block) / (throttle * 1024 * 1024))
            target.flush(); os.fsync(target.fileno())
        after = src.stat()
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise BackupError("original changed during upload: %s" % src)
        with part.open("rb") as stream:
            while True:
                if time.monotonic() >= deadline:
                    raise TimeoutError("max-minutes reached hashing gzip")
                block = stream.read(CHUNK)
                if not block: break
                if heartbeat: heartbeat()
                gz_hash.update(block); gz_size += len(block)
        final = gz_path
        suffix = 1
        while True:
            try:
                os.link(part, final)
                part.unlink()
                break
            except FileExistsError:
                final = gz_path.with_name("%s.%s.%d.gz" % (gz_path.name[:-3], original_hash.hexdigest()[:8], suffix))
                suffix += 1
            except OSError as exc:
                if exc.errno not in (errno.ENOTSUP, errno.EOPNOTSUPP, errno.EXDEV):
                    raise
                # SMB honors O_EXCL even though it does not support hard links.
                try:
                    fd = os.open(final, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                except FileExistsError:
                    final = gz_path.with_name("%s.%s.%d.gz" % (gz_path.name[:-3], original_hash.hexdigest()[:8], suffix))
                    suffix += 1
                    continue
                os.close(fd)
                try:
                    os.replace(part, final)
                except BaseException:
                    with contextlib.suppress(OSError): final.unlink()
                    raise
                break
        return {"size": size, "sha256": original_hash.hexdigest(), "gz_size": gz_size,
                "gz_sha256": gz_hash.hexdigest(), "mtime": before.st_mtime,
                "mtime_ns": before.st_mtime_ns, "remote_name": final.name}
    finally:
        with contextlib.suppress(FileNotFoundError):
            part.unlink()


def _verify(src, gz_path, upload, deadline, throttle, heartbeat=None):
    compressed_hash, raw_hash, gz_size, size = hashlib.sha256(), hashlib.sha256(), 0, 0
    with gz_path.open("rb") as compressed:
        if os.fstat(compressed.fileno()).st_size == 0:
            return False
        while True:
            if time.monotonic() >= deadline: raise TimeoutError("max-minutes reached verifying archive")
            block = compressed.read(CHUNK)
            if not block: break
            if heartbeat: heartbeat()
            compressed_hash.update(block); gz_size += len(block)
    with gzip.open(gz_path, "rb") as decoded:
        while True:
            if time.monotonic() >= deadline: raise TimeoutError("max-minutes reached decompressing archive")
            block = decoded.read(CHUNK)
            if not block: break
            if heartbeat: heartbeat()
            raw_hash.update(block); size += len(block)
    st_before = src.stat()
    original_size, original_hash = _file_hash(src, deadline, throttle, heartbeat)
    st_after = src.stat()
    expected_size, expected_mtime = upload.get("size"), upload.get("mtime_ns")
    return (st_before.st_size, st_before.st_mtime_ns) == (st_after.st_size, st_after.st_mtime_ns) == (expected_size, expected_mtime) and size == expected_size and raw_hash.hexdigest() == upload.get("sha256") == original_hash and original_size == expected_size and gz_size == upload.get("gz_size") and compressed_hash.hexdigest() == upload.get("gz_sha256")


def _watchdog(timeout, callback=os._exit):
    heartbeat_at = [time.monotonic()]
    stopped = threading.Event()
    def beat(): heartbeat_at[0] = time.monotonic()
    def monitor():
        while not stopped.wait(min(0.1, timeout / 10)):
            if time.monotonic() - heartbeat_at[0] > timeout:
                LOG.critical("no file I/O progress for %.1f seconds; terminating", timeout)
                callback(3)
                return
    thread = threading.Thread(target=monitor, daemon=True); thread.start()
    return beat, stopped, thread


def _delete_hashes_match(src, gz_path, upload, deadline=None, throttle=0, heartbeat=None):
    local_size, local_hash = _file_hash(src, deadline, throttle, heartbeat)
    remote_hash, remote_size = hashlib.sha256(), 0
    with gzip.open(gz_path, "rb") as stream:
        for block in iter(lambda: stream.read(CHUNK), b""):
            if deadline is not None and time.monotonic() >= deadline:
                raise TimeoutError("max-minutes reached during pre-delete NAS hash")
            if heartbeat: heartbeat()
            remote_hash.update(block); remote_size += len(block)
    expected = upload.get("sha256")
    return (local_size == remote_size == upload.get("size") and
            local_hash == remote_hash.hexdigest() == expected)


def _restore_tombstone(tomb, original):
    """Restore without replacing a concurrently recreated source path."""
    try:
        if original.exists():
            if os.path.samefile(tomb, original):
                tomb.unlink()
                return True
            if ".late-" in tomb.name:
                LOG.error("ALERT original path exists; late tombstone retained at %s", tomb)
                return False
        os.link(tomb, original)
    except FileExistsError:
        late = tomb.with_name(tomb.name + ".late-%d" % time.time_ns())
        os.rename(tomb, late)
        LOG.error("ALERT original path exists; tombstone retained at %s", late)
        return False
    tomb.unlink()
    return True


def _safe_delete(src, expected, dest, root, args, manifest, upload, current, gz_path=None, deadline=None, throttle=0, heartbeat=None):
    _mount_check(args, root, dest)
    before = src.stat()
    if (before.st_size, before.st_mtime_ns, before.st_ino) != (expected["size"], expected["mtime_ns"], expected["st_ino"]):
        raise BackupError("source changed before deletion")
    if gz_path is None or not _delete_hashes_match(src, gz_path, upload, deadline, throttle, heartbeat):
        raise BackupError("source or decompressed NAS bytes differ from manifest immediately before deletion")
    tomb = src.with_name(src.name + ".deleting-%d" % os.getpid())
    audit = dest / "deleted.jsonl"
    record = {"path": upload.get("path", src.name), "sha256": upload.get("sha256"),
              "upload_id": upload.get("upload_id"), "deleted_at": current.isoformat(),
              "size": upload.get("size")}
    _json_append(audit, {**record, "phase": "intent"})
    os.rename(src, tomb)
    try:
        with tomb.open("rb") as hashed:
            snapshot = os.fstat(hashed.fileno())
            if (snapshot.st_size, snapshot.st_mtime_ns, snapshot.st_ino) != (expected["size"], expected["mtime_ns"], expected["st_ino"]):
                raise BackupError("source changed during deletion rename; retained")
            size, digest = _hash_open_file(hashed, deadline, throttle, heartbeat)
            hashed_after = os.fstat(hashed.fileno())
            path_after = tomb.stat()
            if size != upload.get("size") or digest != upload.get("sha256") or _stat_identity(snapshot) != _stat_identity(hashed_after) or _stat_identity(hashed_after) != _stat_identity(path_after):
                raise BackupError("tombstoned source changed during or after final hash")
            if deadline is not None and time.monotonic() >= deadline:
                raise TimeoutError("max-minutes reached before unlink")
            _mount_check(args, root, dest)
            if _stat_identity(os.fstat(hashed.fileno())) != _stat_identity(hashed_after) or _stat_identity(tomb.stat()) != _stat_identity(hashed_after):
                raise BackupError("tombstone metadata changed immediately before unlink")
            tomb.unlink()
    except Exception:
        if tomb.exists():
            try: _restore_tombstone(tomb, src)
            except OSError: LOG.exception("could not restore tombstone %s", tomb)
        raise
    try: _json_append(audit, {**record, "phase": "complete"})
    except OSError as exc:
        LOG.exception("deleted intent is recorded but completion append failed for %s", src)
        raise BackupError("source was deleted but completion audit append failed: %s" % src) from exc
    _prune_empty_dirs(src, root)


def _prune_empty_dirs(path, root):
    current = path.parent
    while current != root and root in current.parents:
        try: current.rmdir()
        except OSError: break
        current = current.parent


def _args(argv):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dry-run", action="store_true"); p.add_argument("--no-delete", action="store_true")
    p.add_argument("--enable-delete", action="store_true"); p.add_argument("--max-files", type=int)
    p.add_argument("--max-minutes", type=float, default=150); p.add_argument("--io-timeout", type=float, default=300)
    p.add_argument("--hard-kill-grace-seconds", type=float, default=float(os.environ.get(
        "ARCHIVE_NAS_HARD_KILL_GRACE_SECONDS", DEFAULT_HARD_KILL_GRACE_SECONDS)))
    p.add_argument("--only-day", help="limit selection to UTC YYYY-MM-DD")
    p.add_argument("--idle-seconds", type=float, default=30)
    p.add_argument("--report", action="store_true"); p.add_argument("--source", default=str(DEFAULT_SOURCE))
    p.add_argument("--status", action="store_true", help="print the local run status and exit")
    p.add_argument("--dest", default=str(DEFAULT_DEST)); p.add_argument("--mount", default=str(DEFAULT_MOUNT))
    p.add_argument("--state-dir", default=str(DEFAULT_STATE))
    p.add_argument("--keep-days", type=int, default=1); p.add_argument("--close-margin-hours", type=float, default=6)
    p.add_argument("--estimate-ratio", type=float, default=.25)
    p.add_argument("--throttle-mbps", type=float, default=0)
    p.add_argument("--nas-server", default=os.environ.get("ARCHIVE_NAS_SERVER", "noroot.local"))
    p.add_argument("--nas-fallback-host", default=os.environ.get("ARCHIVE_NAS_FALLBACK_HOST", "192.168.0.12"))
    p.add_argument("--nas-user", default=os.environ.get("ARCHIVE_NAS_USER", "88motorcycle"))
    p.add_argument("--nas-share", default=os.environ.get("ARCHIVE_NAS_SHARE", "HDD2TB"))
    p.add_argument("--mount-timeout", type=float, default=90)
    p.add_argument("--mount-wait", type=float, default=60)
    p.add_argument("--no-auto-mount", action="store_true")
    return p.parse_args(argv)


def main(argv=None, now=None):
    process_started = time.monotonic()
    started_epoch = time.time()
    args = _args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", stream=sys.stdout)
    for handler in logging.root.handlers:
        if isinstance(handler, logging.StreamHandler) and handler.stream is sys.stdout:
            handler.addFilter(lambda record: record.levelno < logging.WARNING)
    if not any(isinstance(handler, logging.StreamHandler) and handler.stream is sys.stderr for handler in logging.root.handlers):
        stderr_handler = logging.StreamHandler(sys.stderr)
        stderr_handler.setLevel(logging.WARNING)
        stderr_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logging.root.addHandler(stderr_handler)
    if args.status:
        status_path = Path(args.state_dir) / "archive_to_nas.status.json"
        try:
            status = json.loads(status_path.read_text())
            print(json.dumps(status, sort_keys=True))
            alive = False
            try: os.kill(int(status.get("pid", -1)), 0); alive = True
            except (OSError, ValueError, TypeError): pass
            return 1 if alive and time.time() - float(status.get("last_progress_epoch", 0)) > 600 else 0
        except (OSError, ValueError, TypeError) as exc:
            print(json.dumps({"error": str(exc)})); return 1
    try: os.nice(10)
    except (AttributeError, OSError): pass
    state = Path(args.state_dir)
    readonly = args.dry_run or args.report
    cleanups = []
    if not readonly:
        try: state.mkdir(parents=True, exist_ok=True)
        except OSError as exc: LOG.error("cannot create state directory: %s", exc); return 2
    if readonly:
        lock = None
    else:
        try: lock = (state / "archive_to_nas.lock").open("a+")
        except OSError as exc: LOG.error("cannot open lock: %s", exc); return 2
    try:
        try:
            if lock is not None: fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            lock.seek(0); raw = lock.read().strip(); pid = int(raw) if raw.isdigit() else None
            alive = False
            if pid:
                try: os.kill(pid, 0); alive = True
                except OSError: pass
            LOG.error("lock contention; holder pid=%s alive=%s%s", pid, alive, " (stale lock info; flock is released)" if pid and not alive else "")
            return 2
        if lock is not None:
            lock.seek(0); lock.truncate(); lock.write(str(os.getpid())); lock.flush(); os.fsync(lock.fileno())
        beat, stop_watch, watcher = _watchdog(args.io_timeout)
        hard_stop = threading.Event()
        budget = args.max_minutes * 60 if args.max_minutes else 10**12
        deadline = process_started + budget
        def hard_kill():
            until = deadline + max(0, args.hard_kill_grace_seconds)
            while not hard_stop.wait(min(1, max(0, until - time.monotonic()))):
                if time.monotonic() >= until: os._exit(3)
        hard_watcher = threading.Thread(target=hard_kill, daemon=True); hard_watcher.start()
        cleanups.append(lambda: (stop_watch.set(), hard_stop.set()))  # early returns must not leak os._exit watchers
        status_path = state / "archive_to_nas.status.json"
        status = {"pid": os.getpid(), "stage": "starting", "started_epoch": started_epoch, "last_progress_epoch": time.time()}
        def progress(stage, done=0, total=0, byte_count=0, force=False):
            nonlocal progress_at
            current_time = time.monotonic()
            if force or current_time - progress_at >= 60:
                status.update(stage=stage, last_progress_epoch=time.time(), files_done=done, files_total=total, bytes=byte_count)
                if not readonly and (state / "archive_to_nas.lock").exists():
                    with contextlib.suppress(OSError): _atomic_json(status_path, status)
                LOG.info("progress files=%d/%d bytes=%d stage=%s", done, total, byte_count, stage)
                progress_at = current_time
            beat()
        progress_at = process_started - 60
        status.update(stage="starting", last_progress_epoch=time.time())
        if not readonly and (state / "archive_to_nas.lock").exists():
            with contextlib.suppress(OSError): _atomic_json(status_path, status)
        LOG.info("start pid=%d args=%s", os.getpid(), vars(args))
        progress("starting", force=True)
        root, dest = Path(args.source).resolve(), Path(args.dest)
        def check_deadline():
            if time.monotonic() >= deadline:
                LOG.warning("max-minutes expired; stopping after current stage")
                return False
            return True
        if not root.is_dir(): LOG.error("source directory missing: %s", root); return 2
        current = _utc(now or datetime.now(timezone.utc)); current_epoch = current.timestamp()
        if not readonly and not _ensure_mounted(args, root, dest):
            LOG.error("NAS mount unavailable after automatic mount attempts; no archive data was written")
            return 2
        if not check_deadline(): return 10
        try:
            _preflight(args)
            if not check_deadline(): return 10
        except BackupError as exc:
            LOG.error("preflight failed: %s", exc); return 2
        try:
            progress("scanning NAS", force=True)
            candidates = _scan(root, current, args.close_margin_hours)
            if args.only_day:
                try: datetime.strptime(args.only_day, "%Y-%m-%d")
                except ValueError:
                    LOG.error("--only-day must use YYYY-MM-DD: %s", args.only_day)
                    return 2
                candidates = [x for x in candidates if x[0].strftime("%Y-%m-%d") == args.only_day]
            pending_bytes = sum(x[2].st_size for x in candidates)
            # Recover interrupted local rename transactions conservatively by restoring data.
            if not readonly:
                for artifact in list(root.rglob("*.deleting-*")) + list(root.rglob("*.late-*")):
                    match = re.match(r"^(.*?\.jsonl)\.(?:deleting-\d+(?:\.late-\d+)*|late-\d+(?:\.late-\d+)*)$", artifact.name)
                    if not match: continue
                    original = artifact.with_name(match.group(1))
                    if ".late-" in artifact.name and original.exists():
                        if os.path.samefile(artifact, original):
                            artifact.unlink()
                            continue
                        LOG.error("ALERT retained late tombstone because original path exists: %s", artifact)
                        continue
                    try: _restore_tombstone(artifact, original)
                    except OSError: LOG.exception("could not recover tombstone %s", artifact)
            orphans = ([str(p) for p in root.rglob("*.part")] +
                       [str(p) for p in root.rglob("*.deleting-*")] +
                       [str(p) for p in root.rglob("*.late-*")])
            audit_records = _records(dest / "deleted.jsonl")
            intents = {}
            for item in audit_records:
                key = (item.get("path"), item.get("upload_id"))
                intents[key] = item.get("phase") in ("complete", "abort")
            dangling_intents = [key for key, complete in intents.items() if not complete]
            # Reconcile interrupted rename/delete transactions without leaving a permanent red state.
            for rel_name, upload_id in dangling_intents if not readonly else []:
                src = root / str(rel_name)
                tombs = (list(src.parent.glob(src.name + ".deleting-*")) + list(src.parent.glob(src.name + ".late-*"))) if src.parent.exists() else []
                if tombs:
                    try: _restore_tombstone(tombs[0], src)
                    except OSError: continue
                if src.exists():
                    _json_append(dest / "deleted.jsonl", {"path": rel_name, "upload_id": upload_id, "phase": "abort", "reconciled_at": current.isoformat(), "reason": "local source retained or restored"})
                    intents[(rel_name, upload_id)] = True
                else:
                    rel = Path(str(rel_name)); manifest_path = _manifest(dest, rel)
                    upload = next((r for r in reversed(_records(manifest_path)) if r.get("type", "upload") == "upload" and r.get("upload_id") == upload_id), None)
                    if upload:
                        gz = dest / rel.parent / upload.get("remote_name", rel.name + ".gz")
                        try:
                            compressed_size, compressed_hash = _file_hash(gz)
                            with gzip.open(gz, "rb") as stream: payload_hash = hashlib.sha256(); payload_size = 0
                            with gzip.open(gz, "rb") as stream:
                                for block in iter(lambda: stream.read(CHUNK), b""): payload_hash.update(block); payload_size += len(block)
                            if (compressed_size, compressed_hash, payload_size, payload_hash.hexdigest()) == (upload.get("gz_size"), upload.get("gz_sha256"), upload.get("size"), upload.get("sha256")):
                                _json_append(dest / "deleted.jsonl", {"path": rel_name, "upload_id": upload_id, "phase": "complete", "reconciled_at": current.isoformat(), "reason": "local source absent and NAS copy verified"})
                                intents[(rel_name, upload_id)] = True
                        except (OSError, EOFError, gzip.BadGzipFile): pass
            dangling_intents = [key for key, complete in intents.items() if not complete]
            for orphan in orphans: LOG.error("orphan tombstone requires attention: %s", orphan)
            for item in dangling_intents: LOG.error("deletion intent has no completion record: %s", item[0])
            try: free = shutil.disk_usage(dest).free
            except OSError as exc: LOG.error("cannot read NAS free space: %s", exc); return 2
            if free < pending_bytes * args.estimate_ratio * 2:
                LOG.error("insufficient NAS space: free=%d pending_estimate=%d", free, int(pending_bytes * args.estimate_ratio)); return 2
            if args.report:
                if args.max_files is not None: candidates = candidates[:max(0, args.max_files)]
                pending_bytes = sum(x[2].st_size for x in candidates)
                uploaded = verified = deletable = uploaded_bytes = verified_bytes = deletable_bytes = 0
                for _, src, st in candidates:
                    rel = src.relative_to(root); recs = _records(_manifest(dest, rel)); up = _latest_upload(recs, rel)
                    if up and up.get("upload_id") and (up.get("size"), up.get("mtime_ns")) == (st.st_size, st.st_mtime_ns):
                        gz = dest / rel.parent / up.get("remote_name", src.name + ".gz")
                        if gz.exists():
                            uploaded += 1; uploaded_bytes += st.st_size; v = _verified(recs, rel, up)
                            if v:
                                verified += 1; verified_bytes += st.st_size
                                if _hour_from_path(src, root).date() < (current.date() - timedelta(days=args.keep_days)):
                                    deletable += 1; deletable_bytes += st.st_size
                days = sorted({c[0].strftime("%Y-%m-%d") for c in candidates})
                hours = sorted({c[0].strftime("%Y-%m-%dT%H:00Z") for c in candidates})
                print(json.dumps({"local_pending": len(candidates), "pending_bytes": pending_bytes, "eligible_utc_days": days, "eligible_utc_hours": hours, "close_margin_hours": args.close_margin_hours, "uploaded": uploaded, "uploaded_bytes": uploaded_bytes, "verified": verified, "verified_bytes": verified_bytes, "deletable": deletable, "deletable_bytes": deletable_bytes, "orphan_tombstones": orphans, "dangling_intents": [x[0] for x in dangling_intents], "nas_free_bytes": free}, sort_keys=True)); return 1 if orphans or dangling_intents else 0
            if args.dry_run and args.max_files is not None:
                candidates = candidates[:max(0, args.max_files)]
            progress("processing", 0, len(candidates), pending_bytes, force=True)
            failures = 1 if dangling_intents else 0
            uploaded_count = verified_count = skipped_count = 0
            failure_dir = state / "failures"
            backoff_hours = 6
            def failure_key(src): return hashlib.sha256(src.relative_to(root).as_posix().encode()).hexdigest() + ".json"
            def mark_failure(src, epoch):
                fp = failure_dir / failure_key(src)
                try: old_failure = json.loads(fp.read_text())
                except (OSError, ValueError, TypeError): old_failure = {}
                count = min(10, int(old_failure.get("count", 0)) + 1)
                delay = min(backoff_hours * 3600, 60 * (2 ** min(count - 1, 9)))
                _atomic_json(fp, {"count": count, "retry_after": epoch + delay})
            def clear_failure(src):
                with contextlib.suppress(FileNotFoundError): (failure_dir / failure_key(src)).unlink()
            candidates = [c for c in candidates if _eligible_after_backoff(c[1], failure_dir, failure_key, current_epoch)]
            if args.max_files is not None: candidates = candidates[:max(0, args.max_files)]
            pending_bytes = sum(x[2].st_size for x in candidates)
            deferred_days = 0
            day_groups = sorted({c[0].strftime("%Y-%m-%d") for c in candidates})
            for day in day_groups:
                if time.monotonic() >= deadline:
                    deferred_days += len(day_groups) - day_groups.index(day)
                    LOG.info("deadline reached at day boundary; deferring remaining UTC days from=%s count=%d", day, deferred_days)
                    break
                day_candidates = [c for c in candidates if c[0].strftime("%Y-%m-%d") == day]
                for candidate_index, (_, src, initial) in enumerate(day_candidates, 1):
                    progress("processing", candidate_index - 1, len(candidates), pending_bytes)
                    if time.monotonic() >= deadline: LOG.warning("max-minutes expired; remaining files deferred"); break
                    rel = src.relative_to(root); day_dir = dest / rel.parent
                    try:
                        _mount_check(args, root, dest)
                        if not day_dir.is_dir() and not args.dry_run:
                            day_dir.mkdir(parents=True, exist_ok=True)
                        for stale in day_dir.rglob("*.part") if day_dir.exists() else ():
                            if not stale.is_symlink() and time.time() - stale.stat().st_mtime > 86400 and not args.dry_run:
                                stale.unlink()
                        for stale in day_dir.rglob("*.gz") if day_dir.exists() else ():
                            if not stale.is_symlink() and stale.stat().st_size == 0 and time.time() - stale.stat().st_mtime > 86400 and not args.dry_run:
                                stale.unlink()
                    except BackupError as exc: LOG.critical("mount lost; aborting: %s", exc); return 2
                    try: current_source = os.stat(src, follow_symlinks=False)
                    except OSError as exc: LOG.warning("cannot stat source %s: %s", rel, exc); continue
                    if src.is_symlink() or (current_source.st_size, current_source.st_mtime_ns) != (initial.st_size, initial.st_mtime_ns):
                        LOG.warning("source changed or is symlink; skipping: %s", rel); continue
                    manifest = _manifest(dest, rel); records = _records(manifest); old = _latest_upload(records, rel)
                    source_matches = old and old.get("upload_id") and all(old.get(key) is not None for key in ("size", "mtime_ns", "sha256", "gz_size", "gz_sha256")) and (old.get("size"), old.get("mtime_ns")) == (initial.st_size, initial.st_mtime_ns)
                    invalid_after_upload = any(r.get("type") == "invalid" and r.get("upload_id") == old.get("upload_id") for r in records) if old else False
                    upload = old if source_matches and not invalid_after_upload else None
                    if not upload and old and not old.get("upload_id"):
                        legacy_remote = dest / rel.parent / old.get("remote_name", src.name + ".gz")
                        try:
                            pre_size, pre_hash = _file_hash(src, deadline, args.throttle_mbps, beat)
                            gz_size, gz_hash = _file_hash(legacy_remote)
                            legacy = {**old, "size": pre_size, "mtime_ns": initial.st_mtime_ns, "sha256": pre_hash,
                                      "gz_size": gz_size, "gz_sha256": gz_hash}
                            if _verify(src, legacy_remote, legacy, deadline, args.throttle_mbps, beat):
                                upload = {**legacy, "type": "upload", "path": rel.as_posix(),
                                          "upload_id": datetime.fromtimestamp(current_epoch, timezone.utc).isoformat() + "-" + pre_hash[:8],
                                          "remote_name": legacy_remote.name,
                                          "uploaded_at": datetime.fromtimestamp(current_epoch, timezone.utc).isoformat()}
                                if not readonly: _json_append(manifest, upload)
                                uploaded_count += 1
                                LOG.info("adopted legacy verified archive without duplicate upload: %s", rel)
                        except (OSError, EOFError, gzip.BadGzipFile, zlib.error, TimeoutError):
                            upload = None
                    if not upload:
                        if args.dry_run:
                            LOG.info("PLAN upload+verify %s (%d bytes)", rel, initial.st_size); continue
                        try:
                            _mount_check(args, root, dest)
                            pre_size, pre_hash = _file_hash(src, deadline, args.throttle_mbps, beat)
                            base_remote_name = src.name + ("." + pre_hash[:8] if old else "") + ".gz"
                            remote_name = base_remote_name
                            remote = dest / rel.parent / remote_name
                            if remote.exists():
                                try:
                                    with gzip.open(remote, "rb") as existing:
                                        digest = hashlib.sha256()
                                        while True:
                                            block = existing.read(CHUNK)
                                            if not block: break
                                            digest.update(block); beat()
                                        existing_hash = digest.hexdigest()
                                except (OSError, EOFError, gzip.BadGzipFile): existing_hash = None
                                if existing_hash != pre_hash:
                                    remote_name = src.name + "." + pre_hash[:8] + ".%d.gz" % time.time_ns()
                                    remote = dest / rel.parent / remote_name
                            data = _copy_gzip(src, remote, deadline, args.throttle_mbps, beat)
                            remote_name = data.pop("remote_name")
                            upload_id = datetime.fromtimestamp(current_epoch, timezone.utc).isoformat() + "-" + data["sha256"][:8]
                            if pre_size != data["size"] or pre_hash != data["sha256"]:
                                raise BackupError("source changed while preparing versioned upload")
                            upload = {"type": "upload", "path": rel.as_posix(), **data, "uploaded_at": datetime.fromtimestamp(current_epoch, timezone.utc).isoformat(), "upload_id": upload_id, "remote_name": remote_name}
                            _json_append(manifest, upload)
                            uploaded_count += 1
                        except BackupError as exc:
                            if "mount" in str(exc).lower(): LOG.critical("mount lost; aborting: %s", exc); return 2
                            LOG.warning("upload deferred for %s: %s", rel, exc); failures += 1; mark_failure(src, current_epoch); continue
                        except (OSError, TimeoutError) as exc:
                            if isinstance(exc, TimeoutError) and time.monotonic() >= deadline:
                                LOG.info("deadline during upload; deferring remainder of UTC day=%s", day)
                                break
                            LOG.warning("upload deferred for %s: %s", rel, exc); failures += 1; mark_failure(src, current_epoch); continue
                    gz = dest / rel.parent / upload.get("remote_name", src.name + ".gz")
                    progress("verifying", candidate_index - 1, len(candidates), pending_bytes, force=True)
                    try: valid = _verify(src, gz, upload, deadline, args.throttle_mbps, beat)
                    except (EOFError, gzip.BadGzipFile, zlib.error) as exc:
                        if not readonly: _json_append(manifest, {"type": "invalid", "path": rel.as_posix(), "sha256": upload.get("sha256"), "upload_id": upload.get("upload_id"), "invalid_at": datetime.fromtimestamp(current_epoch, timezone.utc).isoformat()})
                        LOG.warning("invalid NAS content for %s: %s", rel, exc); failures += 1; mark_failure(src, current_epoch); continue
                    except (OSError, TimeoutError) as exc:
                        if isinstance(exc, TimeoutError) and time.monotonic() >= deadline:
                            LOG.info("deadline during verification; deferring remainder of UTC day=%s", day)
                            break
                        LOG.warning("verification deferred for %s: %s", rel, exc); failures += 1; mark_failure(src, current_epoch); continue
                    if not valid:
                        if not readonly: _json_append(manifest, {"type": "invalid", "path": rel.as_posix(), "sha256": upload.get("sha256"), "upload_id": upload.get("upload_id"), "invalid_at": datetime.fromtimestamp(current_epoch, timezone.utc).isoformat()})
                        failures += 1; mark_failure(src, current_epoch); continue
                    verified_count += 1
                    if not readonly and not _verified(_records(manifest), rel, upload):
                        _json_append(manifest, {"type": "verified", "path": rel.as_posix(), "sha256": upload.get("sha256"), "upload_id": upload.get("upload_id"), "verified_at": datetime.fromtimestamp(current_epoch, timezone.utc).isoformat()})
                        pass
                    if not readonly: clear_failure(src)
                if args.dry_run:
                    continue
            # Day-level barrier: re-scan after this day upload, then freshly hash local and NAS copies.
                if time.monotonic() >= deadline:
                    deferred_days += 1
                    LOG.info("deadline reached at day boundary; deferring UTC day=%s", day)
                    continue
                day_files = [x for x in _scan(root, current, args.close_margin_hours) if x[0].strftime("%Y-%m-%d") == day]
                day_files.sort(key=lambda x: (x[0], str(x[1])))
                valid_records = []
                day_ok = bool(day_files)
                day_deferred = False
                for _, src, st in day_files:
                    rel = src.relative_to(root); manifest = _manifest(dest, rel); records = _records(manifest)
                    upload = _latest_upload(records, rel)
                    if not upload or not upload.get("upload_id") or (upload.get("size"), upload.get("mtime_ns")) != (st.st_size, st.st_mtime_ns):
                        day_ok = False; break
                    gz = dest / rel.parent / upload.get("remote_name", src.name + ".gz")
                    try: valid = _verify(src, gz, upload, deadline, args.throttle_mbps, beat)
                    except TimeoutError:
                        day_deferred = True
                        break
                    except (OSError, EOFError, gzip.BadGzipFile, zlib.error): valid = False
                    if not valid or Path(str(gz) + ".part").exists():
                        day_ok = False; break
                    valid_records.append((src, st, rel, manifest, upload, gz))
                if day_deferred:
                    deferred_days += 1
                    LOG.info("deadline during day completeness scan; deferring UTC day=%s", day)
                    continue
                nas_day = dest / day[:4] / day[5:7] / day[8:10]
                local_day = root / day[:4] / day[5:7] / day[8:10]
                if local_day.exists() and any(path for pattern in ("*.part", "*.deleting-*", "*.late-*") for path in local_day.rglob(pattern)):
                    day_ok = False
                if nas_day.exists() and any(path for pattern in ("*.part", "*.deleting-*", "*.late-*") for path in nas_day.rglob(pattern)):
                    day_ok = False
                deletion_deferred = False
                if day_ok:
                    digest = hashlib.sha256("\n".join(sorted(x[4]["sha256"] for x in valid_records)).encode()).hexdigest()
                    record = {"type": "day_complete", "day": day, "file_count": len(valid_records), "total_bytes": sum(x[1].st_size for x in valid_records), "sha256_list_digest": digest, "completed_at": current.isoformat()}
                    if not readonly:
                        _json_append(dest / day[:4] / day[5:7] / day[8:10] / "manifest.jsonl", record)
                        _atomic_json(state / ("day-complete-" + day + ".json"), record)
                    if args.enable_delete and not args.no_delete and not readonly and datetime.strptime(day, "%Y-%m-%d").date() < current.date() - timedelta(days=args.keep_days):
                        # Verify the complete delete set before starting any deletion.
                        stable_set = []
                        try:
                            for src, st, rel, manifest, upload, gz in valid_records:
                                fresh = os.stat(src, follow_symlinks=False)
                                if (fresh.st_size, fresh.st_mtime_ns, fresh.st_ino) != (st.st_size, st.st_mtime_ns, st.st_ino) or not _verify(src, gz, upload, deadline, args.throttle_mbps, beat):
                                    raise BackupError("source changed or fresh verify failed")
                                gz_stat = gz.stat()
                                stable_set.append((src, st, rel, manifest, upload, gz, fresh, (gz_stat.st_size, gz_stat.st_mtime_ns)))
                            if args.idle_seconds > 0: time.sleep(args.idle_seconds)
                            for src, st, rel, manifest, upload, gz, fresh, gz_identity in stable_set:
                                stable = os.stat(src, follow_symlinks=False)
                                if (stable.st_size, stable.st_mtime_ns, stable.st_ino) != (fresh.st_size, fresh.st_mtime_ns, fresh.st_ino):
                                    raise BackupError("source changed during day idle check")
                                gz_after = gz.stat()
                                if (gz_after.st_size, gz_after.st_mtime_ns) != gz_identity:
                                    raise BackupError("NAS archive changed during day idle check")
                        except TimeoutError:
                            LOG.info("deadline during day verification; deferring deletion for UTC day=%s", day)
                            deferred_days += 1
                            day_ok = False
                            continue
                        except (BackupError, OSError, EOFError, zlib.error) as exc:
                            LOG.error("ALERT pre-delete day verification failed for %s: %s", day, exc)
                            failures += 1; day_ok = False
                        if day_ok:
                            for src, st, rel, manifest, upload, gz, stable, _ in stable_set:
                                grace_end = deadline + max(0, args.hard_kill_grace_seconds)
                                safety_margin = min(60, max(5, args.hard_kill_grace_seconds // 5))
                                available = grace_end - safety_margin - time.monotonic()
                                per_file_estimate = 30.0
                                if args.throttle_mbps > 0:
                                    per_file_estimate += (stable.st_size * 3) / (args.throttle_mbps * 1024 * 1024)
                                if available <= per_file_estimate:
                                    LOG.info("hard-kill grace approaching; deferring remaining deletions for UTC day=%s", day)
                                    deferred_days += 1
                                    deletion_deferred = True
                                    day_ok = False
                                    break
                                try:
                                    _safe_delete(src, {"size": upload["size"], "mtime_ns": upload["mtime_ns"], "st_ino": stable.st_ino}, dest, root, args, manifest, upload, current, gz, grace_end - safety_margin, args.throttle_mbps, beat)
                                except TimeoutError as exc:
                                    LOG.info("deletion transaction reached grace cutoff; deferring remaining files for UTC day=%s: %s", day, exc)
                                    deferred_days += 1
                                    deletion_deferred = True
                                    day_ok = False
                                    break
                                except (BackupError, OSError, EOFError, zlib.error) as exc:
                                    LOG.error("ALERT deletion/audit failed for %s; inspect local path and NAS deletion audit: %s", rel, exc)
                                    day_ok = False; failures += 1; break
                if deletion_deferred:
                    continue
                if not day_ok:
                    LOG.error("ALERT day completion/deletion failed; inspect local files and deletion audit: %s (local_files=%d verified=%d)", day, len(day_files), len(valid_records))
                    failures += 1
                else:
                    LOG.info("day complete UTC=%s files=%d bytes=%d", day, len(day_files), sum(x[2].st_size for x in day_files))
                if time.monotonic() >= deadline:
                    remaining_days = len(day_groups) - day_groups.index(day) - 1
                    deferred_days += remaining_days
                    if remaining_days:
                        LOG.info("deadline crossed during day transaction; UTC day finished; deferring remaining work count=%d", remaining_days)
                        break
            status.update(stage="complete", last_progress_epoch=time.time(), files_done=len(candidates), files_total=len(candidates), bytes=pending_bytes)
            if not readonly:
                with contextlib.suppress(OSError): _atomic_json(status_path, status)
            LOG.info("summary uploaded=%d verified=%d skipped=%d failed=%d elapsed=%.1fs", uploaded_count, verified_count, skipped_count, failures, time.monotonic()-process_started)
            LOG.info("deferred_days=%d", deferred_days)
            return 1 if failures else (10 if deferred_days else 0)
        finally:
            stop_watch.set(); watcher.join(timeout=1); hard_stop.set(); hard_watcher.join(timeout=1)
    finally:
        for cleanup in cleanups: cleanup()
        if lock is not None: lock.close()


if __name__ == "__main__": sys.exit(main())
