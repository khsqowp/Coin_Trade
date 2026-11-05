import fcntl
import gzip
import importlib.util
import json
import os
import gzip
import subprocess
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/archive_to_nas.py"
spec = importlib.util.spec_from_file_location("archive_to_nas", SCRIPT)
job = importlib.util.module_from_spec(spec)
spec.loader.exec_module(job)


@pytest.fixture
def env(tmp_path, monkeypatch):
    root = tmp_path / "source"
    dest = tmp_path / "nas" / "Trade/tick-archive"
    mount = tmp_path / "nas"
    root.mkdir()
    dest.mkdir(parents=True)
    monkeypatch.setattr(job, "MOUNT_CHECK", lambda mount, dest, root: True)
    return root, dest, mount, tmp_path / "state"


def add_file(env, hour, name="ticks.jsonl", content=b'{"x":1}\n', mtime=None):
    root, _, _, _ = env
    # Fixtures representing the just-finished UTC date are shifted to the previous UTC date;
    # eligibility is day-based now, not an hourly two-hour heuristic.
    if hour.date() == fixed_now().date():
        hour -= timedelta(days=1)
    path = root / hour.strftime("%Y/%m/%d/%H") / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    if mtime is not None:
        os.utime(path, (mtime, mtime))
    return path


def run(env, extra=(), now=None):
    root, dest, mount, state = env
    return job.main(["--source", str(root), "--dest", str(dest), "--mount", str(mount), "--state-dir", str(state), "--idle-seconds", "0", *extra], now=now)


def fixed_now():
    return datetime(2026, 11, 4, 12, tzinfo=timezone.utc)


def test_closed_vs_open_selection(env):
    now = fixed_now()
    closed = add_file(env, now - timedelta(hours=4), mtime=(now - timedelta(hours=3)).timestamp())
    open_hour = env[0] / now.strftime("%Y/%m/%d/%H") / "open.jsonl"
    open_hour.parent.mkdir(parents=True, exist_ok=True); open_hour.write_text("open")
    os.utime(open_hour, (now.timestamp(), now.timestamp()))
    assert run(env, ["--dry-run"], now) == 0
    assert closed.exists() and open_hour.exists()
    assert not list(env[1].rglob("*.gz"))


@pytest.mark.parametrize("now,expected", [
    (datetime(2026, 11, 5, 5, 59, tzinfo=timezone.utc), False),
    (datetime(2026, 11, 5, 6, 0, tzinfo=timezone.utc), True),
])
def test_utc_day_close_margin_boundary(env, now, expected):
    # Nov 4 ended at 00:00 UTC Nov 5; the six-hour margin ends at 06:00 UTC.
    path = env[0] / "2026/11/04/12/file.jsonl"
    path.parent.mkdir(parents=True); path.write_bytes(b"test")
    found = [item[1] for item in job._scan(env[0], now, 6)]
    assert (path in found) is expected


def test_late_file_added_during_upload_blocks_day_completion_and_delete(env, monkeypatch):
    now = fixed_now()
    path = add_file(env, now - timedelta(days=9), "first.jsonl", mtime=(now - timedelta(days=8)).timestamp())
    original = job._copy_gzip
    injected = [False]
    def add_late(src, *args, **kwargs):
        result = original(src, *args, **kwargs)
        if not injected[0]:
            injected[0] = True
            late = src.with_name("late.jsonl")
            late.write_bytes(b"late data")
            os.utime(late, (src.stat().st_mtime, src.stat().st_mtime))
        return result
    monkeypatch.setattr(job, "_copy_gzip", add_late)
    assert run(env, ["--enable-delete"], now) != 0
    assert path.exists()
    assert (path.parent / "late.jsonl").exists()
    assert not list((env[1] / path.relative_to(env[0]).parent.parent).glob("manifest.jsonl")) or not any(
        r.get("type") == "day_complete" for r in map(json.loads, (env[1] / path.relative_to(env[0]).parent.parent / "manifest.jsonl").read_text().splitlines())
    )


def test_same_run_verified_complete_day_deletes_with_audit(env):
    now = fixed_now()
    path = add_file(env, now - timedelta(days=9), mtime=(now - timedelta(days=8)).timestamp())
    assert run(env, ["--enable-delete"], now) == 0
    assert not path.exists()
    audit = [json.loads(x) for x in (env[1] / "deleted.jsonl").read_text().splitlines()]
    assert [item["phase"] for item in audit] == ["intent", "complete"]
    completed = list(env[3].glob("day-complete-*.json"))
    assert len(completed) == 1
    assert json.loads(completed[0].read_text())["file_count"] == 1


def test_no_delete_overrides_enable_delete(env):
    now = fixed_now()
    path = add_file(env, now - timedelta(days=9), mtime=(now - timedelta(days=8)).timestamp())
    assert run(env, ["--enable-delete", "--no-delete"], now) == 0
    assert path.exists()


def test_report_names_eligible_utc_day_and_hours(env, capsys):
    now = fixed_now()
    path = add_file(env, now - timedelta(days=9), mtime=(now - timedelta(days=8)).timestamp())
    assert run(env, ["--report"], now) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["eligible_utc_days"] == [path.relative_to(env[0]).parts[0] + "-" + path.relative_to(env[0]).parts[1] + "-" + path.relative_to(env[0]).parts[2]]
    assert report["eligible_utc_hours"] == ["2026-10-26T12:00Z"]


def test_keep_days_retains_yesterday(env):
    now = fixed_now()
    path = add_file(env, now - timedelta(days=1), mtime=(now - timedelta(days=1)).timestamp())
    assert run(env, ["--enable-delete", "--keep-days", "1"], now) == 0
    assert path.exists()


def test_backlog_is_oldest_first(env, caplog):
    caplog.set_level("INFO")
    now = fixed_now()
    older = add_file(env, now - timedelta(days=12), "older.jsonl", mtime=(now - timedelta(days=11)).timestamp())
    newer = add_file(env, now - timedelta(days=10), "newer.jsonl", mtime=(now - timedelta(days=9)).timestamp())
    actual = []
    original = job._copy_gzip
    def track(src, *args, **kwargs):
        actual.append(src)
        return original(src, *args, **kwargs)
    job._copy_gzip = track
    assert run(env, ["--no-delete"], now) == 0
    job._copy_gzip = original
    assert older.exists() and newer.exists()
    assert actual == [older, newer]


def test_mount_missing_aborts_and_preserves_source(env, monkeypatch):
    path = add_file(env, fixed_now() - timedelta(days=9), mtime=(fixed_now() - timedelta(days=8)).timestamp())
    monkeypatch.setattr(job, "MOUNT_CHECK", lambda mount, dest, root: False)
    assert run(env, now=fixed_now()) != 0
    assert path.exists()


def test_already_mounted_does_not_call_runner(env, monkeypatch):
    called = []
    monkeypatch.setattr(job, "MOUNT_RUNNER", lambda argv, timeout: called.append(argv) or 0)
    assert run(env, ["--no-delete"], fixed_now()) == 0
    assert called == []


def test_ensure_mount_first_host_and_proceed(env, monkeypatch):
    mounted = [False]
    monkeypatch.setattr(job, "MOUNT_CHECK", lambda mount, dest, root: mounted[0])
    calls = []
    def runner(argv, timeout):
        calls.append((argv, timeout)); mounted[0] = True
        return 0
    monkeypatch.setattr(job, "MOUNT_RUNNER", runner)
    monkeypatch.setattr(job, "MOUNT_SLEEP", lambda seconds: None)
    assert run(env, ["--no-delete", "--mount-wait", "0"], fixed_now()) == 0
    assert calls[0][0] == ["open", "-g", "-j", "smb://88motorcycle@noroot.local/HDD2TB"]


def test_nonzero_first_host_uses_fallback(env, monkeypatch):
    mounted = [False]; calls = []
    monkeypatch.setattr(job, "MOUNT_CHECK", lambda mount, dest, root: mounted[0])
    def runner(argv, timeout):
        calls.append(argv)
        if len(calls) == 1: return 1
        mounted[0] = True
        return 0
    monkeypatch.setattr(job, "MOUNT_RUNNER", runner)
    monkeypatch.setattr(job, "MOUNT_SLEEP", lambda seconds: None)
    assert run(env, ["--no-delete", "--mount-wait", "0"], fixed_now()) == 0
    assert calls == [["open", "-g", "-j", "smb://88motorcycle@noroot.local/HDD2TB"],
                     ["open", "-g", "-j", "smb://88motorcycle@192.168.0.12/HDD2TB"]]


def test_mount_failure_does_not_create_mount_or_touch_source(env, monkeypatch, caplog):
    root, dest, _, state = env
    mount = root.parent / "missing-mount"
    path = add_file(env, fixed_now() - timedelta(days=9), mtime=(fixed_now() - timedelta(days=8)).timestamp())
    monkeypatch.setattr(job, "MOUNT_CHECK", lambda mount, dest, root: False)
    monkeypatch.setattr(job, "MOUNT_RUNNER", lambda argv, timeout: 1)
    monkeypatch.setattr(job, "MOUNT_SLEEP", lambda seconds: None)
    monkeypatch.setenv("ARCHIVE_NAS_PASSWORD", "never-log-this-secret")
    caplog.set_level("INFO")
    result = job.main(["--source", str(root), "--dest", str(dest), "--mount", str(mount),
                       "--state-dir", str(state), "--mount-wait", "0"])
    assert result == 2
    assert not mount.exists() and path.exists()
    assert sorted(p.name for p in state.iterdir()) == ["archive_to_nas.lock", "archive_to_nas.status.json"]
    assert "never-log-this-secret" not in caplog.text
    assert "smb://88motorcycle@noroot.local/HDD2TB" not in caplog.text


@pytest.mark.parametrize("extra", [["--dry-run"], ["--report"]])
def test_readonly_modes_never_call_mount_runner(env, monkeypatch, extra):
    called = []
    monkeypatch.setattr(job, "MOUNT_CHECK", lambda mount, dest, root: False)
    monkeypatch.setattr(job, "MOUNT_RUNNER", lambda argv, timeout: called.append(argv) or 0)
    run(env, extra, fixed_now())
    assert called == []


def test_mount_timeout_is_caught_and_falls_back_to_second_host(env, monkeypatch):
    mounted = [False]; calls = []
    monkeypatch.setattr(job, "MOUNT_CHECK", lambda mount, dest, root: mounted[0])
    def runner(argv, timeout):
        calls.append(argv)
        if len(calls) == 1: raise subprocess.TimeoutExpired(argv, timeout)
        mounted[0] = True
        return 0
    monkeypatch.setattr(job, "MOUNT_RUNNER", runner)
    monkeypatch.setattr(job, "MOUNT_SLEEP", lambda seconds: None)
    assert run(env, ["--no-delete", "--mount-wait", "0"], fixed_now()) == 0
    assert len(calls) == 2


def test_no_auto_mount_skips_runner(env, monkeypatch):
    monkeypatch.setattr(job, "MOUNT_CHECK", lambda mount, dest, root: False)
    called = []
    monkeypatch.setattr(job, "MOUNT_RUNNER", lambda argv, timeout: called.append(argv) or 0)
    assert run(env, ["--no-auto-mount"], fixed_now()) == 2
    assert called == []


def test_plain_local_dir_is_not_mount():
    assert not job.is_real_mount("/tmp")


def test_production_mount_check_fails_closed_on_plain_tmp(tmp_path):
    root = tmp_path / "source"; root.mkdir()
    dest = tmp_path / "nas"; dest.mkdir()
    args = job._args(["--source", str(root), "--dest", str(dest), "--mount", str(tmp_path)])
    with pytest.raises(job.BackupError): job._mount_check(args, root, dest)


def test_corrupted_nas_copy_blocks_deletion(env):
    now = fixed_now()
    path = add_file(env, now - timedelta(days=9), mtime=(now - timedelta(days=8)).timestamp())
    assert run(env, ["--no-delete"], now) == 0
    gz = env[1] / path.relative_to(env[0]).parent / (path.name + ".gz")
    gz.write_bytes(b"x" * gz.stat().st_size)
    assert run(env, now=now + timedelta(days=3)) != 0
    assert path.exists()
    assert run(env, ["--no-delete"], now=now + timedelta(days=3)) == 0
    assert path.exists()


def test_missing_nas_copy_blocks_day_completion_and_delete(env):
    now = fixed_now()
    path = add_file(env, now - timedelta(days=9), mtime=(now - timedelta(days=8)).timestamp())
    assert run(env, ["--no-delete"], now) == 0
    gz = env[1] / path.relative_to(env[0]).parent / (path.name + ".gz")
    gz.unlink()
    assert run(env, ["--enable-delete"], now + timedelta(hours=1)) != 0
    assert path.exists()


def test_same_size_local_mismatch_blocks_delete(env):
    now = fixed_now()
    path = add_file(env, now - timedelta(days=9), mtime=(now - timedelta(days=8)).timestamp())
    assert run(env, ["--no-delete"], now) == 0
    before = path.stat()
    data = path.read_bytes()
    path.write_bytes(bytes([data[0] ^ 1]) + data[1:])
    os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
    assert run(env, ["--enable-delete"], now + timedelta(hours=1)) != 0
    assert path.exists()


def test_same_run_completion_replaces_cross_run_grace_and_seven_day_retention(env):
    now = fixed_now()
    old = add_file(env, now - timedelta(days=9), "old.jsonl", mtime=(now - timedelta(days=8)).timestamp())
    recent = add_file(env, now - timedelta(days=2), "recent.jsonl", mtime=(now - timedelta(days=1)).timestamp())
    assert run(env, now=now) == 0
    assert old.exists() and recent.exists()
    assert run(env, ["--enable-delete"], now=now + timedelta(hours=25)) == 0
    assert not old.exists()
    assert not recent.exists()  # two UTC days old; only today and yesterday remain local


def test_idempotency_second_run_does_not_upload_again(env):
    now = fixed_now()
    path = add_file(env, now - timedelta(hours=4), mtime=(now - timedelta(hours=3)).timestamp())
    assert run(env, ["--no-delete"], now) == 0
    manifest = env[1] / path.relative_to(env[0]).parent.parent / "manifest.jsonl"
    count = len(manifest.read_text().splitlines())
    assert run(env, ["--no-delete"], now) == 0
    lines = [json.loads(x) for x in manifest.read_text().splitlines()]
    assert sum(x.get("type", "upload") == "upload" for x in lines) == 1
    assert len(manifest.read_text().splitlines()) == count + 1  # one fresh per-run day-completion record
    assert sum(item.get("type") == "day_complete" for item in lines) == 2


def test_leftover_part_is_overwritten(env):
    now = fixed_now()
    path = add_file(env, now - timedelta(hours=4), mtime=(now - timedelta(hours=3)).timestamp())
    gz = env[1] / path.relative_to(env[0]).parent / (path.name + ".gz")
    gz.parent.mkdir(parents=True)
    Path(str(gz) + ".part").write_bytes(b"crash")
    assert run(env, ["--no-delete"], now) == 0
    with gzip.open(gz, "rb") as stream:
        assert stream.read() == path.read_bytes()
    assert not Path(str(gz) + ".part").exists()


def test_smb_exclusive_reservation_preserves_competing_writer(env, monkeypatch):
    now = fixed_now(); path = add_file(env, now - timedelta(hours=4), mtime=(now - timedelta(hours=3)).timestamp())
    gz = env[1] / path.relative_to(env[0]).parent / (path.name + ".gz")
    original_link = job.os.link
    injected = [False]
    def unsupported_link(src, dst):
        if not injected[0]:
            injected[0] = True
            Path(dst).write_bytes(b"competing-writer-copy")
        raise OSError(45, "Operation not supported")
    monkeypatch.setattr(job.os, "link", unsupported_link)
    assert run(env, ["--no-delete"], now) == 0
    assert gz.read_bytes() == b"competing-writer-copy"
    versions = list(gz.parent.glob("ticks.jsonl.*.gz"))
    assert len(versions) == 1
    with gzip.open(versions[0], "rb") as stream:
        assert stream.read() == path.read_bytes()
    monkeypatch.setattr(job.os, "link", original_link)


def test_zero_length_gzip_is_not_verified_and_stale_placeholder_swept(env):
    now = fixed_now(); path = add_file(env, now - timedelta(hours=4), mtime=(now - timedelta(hours=3)).timestamp())
    assert run(env, ["--no-delete"], now) == 0
    gz = env[1] / path.relative_to(env[0]).parent / (path.name + ".gz")
    gz.write_bytes(b"")
    assert run(env, ["--no-delete"], now + timedelta(minutes=1)) != 0
    os.utime(gz, (time.time() - 90000,) * 2)
    assert run(env, ["--no-delete"], now + timedelta(minutes=2)) == 0
    assert not gz.exists() and list(gz.parent.glob("ticks.jsonl.*.gz"))


def test_original_modified_during_run_is_not_deleted(env, monkeypatch):
    now = fixed_now()
    path = add_file(env, now - timedelta(days=9), mtime=(now - timedelta(days=8)).timestamp())
    original_verify = job._verify

    def modify_then_verify(src, *args):
        src.write_bytes(src.read_bytes() + b"changed")
        return original_verify(src, *args)

    monkeypatch.setattr(job, "_verify", modify_then_verify)
    assert run(env, now=now) != 0
    assert path.exists()


def test_dry_run_writes_nothing(env):
    now = fixed_now()
    path = add_file(env, now - timedelta(hours=4), mtime=(now - timedelta(hours=3)).timestamp())
    before = sorted(str(p.relative_to(env[1])) for p in env[1].rglob("*"))
    assert run(env, ["--dry-run"], now) == 0
    assert sorted(str(p.relative_to(env[1])) for p in env[1].rglob("*")) == before
    assert path.exists()


def test_flock_prevents_concurrent_run(env):
    state = env[3]
    state.mkdir()
    with (state / "archive_to_nas.lock").open("a+") as held:
        fcntl.flock(held.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert run(env, ["--dry-run"], fixed_now()) == 0  # read-only runs intentionally skip lock creation


def test_late_append_creates_versioned_copy_and_keeps_old(env):
    now = fixed_now(); path = add_file(env, now - timedelta(hours=4), mtime=(now - timedelta(hours=3)).timestamp())
    assert run(env, now=now) == 0
    old = env[1] / path.relative_to(env[0]).parent / (path.name + ".gz")
    old_bytes = old.read_bytes()
    path.write_bytes(path.read_bytes() + b"late\n")
    os.utime(path, ns=(path.stat().st_atime_ns, int((now - timedelta(hours=3)).timestamp() * 1e9) + 2_000_000))
    assert run(env, now=now + timedelta(minutes=1)) == 0
    assert run(env, now=now + timedelta(minutes=2)) == 0
    assert old.read_bytes() == old_bytes
    assert list(old.parent.glob(path.name + ".*.gz"))


def test_manifest_lost_and_late_recreated_file_keeps_both_gz_copies(env):
    now = fixed_now(); path = add_file(env, now - timedelta(hours=4), mtime=(now - timedelta(hours=3)).timestamp())
    assert run(env, ["--no-delete"], now) == 0
    day_manifest = env[1] / path.relative_to(env[0]).parent.parent / "manifest.jsonl"
    old_gz = env[1] / path.relative_to(env[0]).parent / "ticks.jsonl.gz"
    original_gz = old_gz.read_bytes()
    day_manifest.unlink()
    path.write_bytes(b"late")
    late_mtime_ns = int(((now - timedelta(hours=3)).timestamp() + 10) * 1_000_000_000)
    os.utime(path, ns=(late_mtime_ns, late_mtime_ns))
    assert run(env, ["--no-delete"], now + timedelta(minutes=3)) == 0
    assert old_gz.read_bytes() == original_gz
    assert len(list(old_gz.parent.glob("ticks.jsonl.*.gz"))) == 1


def test_legacy_upload_without_id_is_refreshed_and_same_run_delete_audited(env):
    now = fixed_now(); path = add_file(env, now - timedelta(days=9), mtime=(now - timedelta(days=8)).timestamp())
    assert run(env, ["--no-delete"], now) == 0
    manifest = env[1] / path.relative_to(env[0]).parent.parent / "manifest.jsonl"
    records = [json.loads(line) for line in manifest.read_text().splitlines()]
    for item in records:
        item.pop("upload_id", None)
    manifest.write_text("".join(json.dumps(item) + "\n" for item in records))
    assert run(env, ["--enable-delete"], now + timedelta(hours=25)) == 0
    assert not path.exists()
    assert len(list((env[1] / path.relative_to(env[0]).parent).glob(path.name + "*.gz"))) == 1
    audit = [json.loads(line) for line in (env[1] / "deleted.jsonl").read_text().splitlines()]
    assert [r["phase"] for r in audit] == ["intent", "complete"]


def test_corrupt_truncated_gzip_is_per_file_failure_without_traceback(env, caplog):
    now = fixed_now(); path = add_file(env, now - timedelta(days=9), mtime=(now - timedelta(days=8)).timestamp())
    assert run(env, ["--no-delete"], now) == 0
    gz = env[1] / path.relative_to(env[0]).parent / (path.name + ".gz")
    gz.write_bytes(b"\x1f\x8b\x08\x00truncated")
    result = run(env, ["--enable-delete"], now + timedelta(hours=25))
    assert result == 1
    assert path.exists()
    assert not any(record.exc_info for record in caplog.records)


@pytest.mark.parametrize("mode", ["--dry-run", "--report"])
def test_readonly_corrupt_gzip_does_not_create_or_change_state(env, mode):
    now = fixed_now(); path = add_file(env, now - timedelta(days=9), mtime=(now - timedelta(days=8)).timestamp())
    assert run(env, ["--no-delete"], now) == 0
    gz = env[1] / path.relative_to(env[0]).parent / (path.name + ".gz")
    gz.write_bytes(b"\x1f\x8b\x08\x00truncated")
    state = env[3]
    before = {str(p.relative_to(state)): (p.read_bytes(), p.stat().st_mtime_ns)
              for p in state.rglob("*") if p.is_file()} if state.exists() else None
    result = job.main(["--source", str(env[0]), "--dest", str(env[1]), "--mount", str(env[2]),
                       "--state-dir", str(state), mode], now=now + timedelta(hours=25))
    assert result == (1 if mode == "--dry-run" else 0)
    after = {str(p.relative_to(state)): (p.read_bytes(), p.stat().st_mtime_ns)
             for p in state.rglob("*") if p.is_file()} if state.exists() else None
    assert after == before


def test_truncated_gzip_at_delete_stage_isolated_and_other_day_continues(env, monkeypatch, caplog):
    now = fixed_now()
    first = add_file(env, now - timedelta(days=9), "first.jsonl", mtime=(now - timedelta(days=8)).timestamp())
    second = add_file(env, now - timedelta(days=8), "second.jsonl", mtime=(now - timedelta(days=7)).timestamp())
    assert run(env, ["--no-delete"], now) == 0
    original_verify = job._verify
    counts = {}
    def corrupt_at_predelete(src, *args):
        count = counts.get(src, 0) + 1
        counts[src] = count
        if src == first and count == 3:
            raise EOFError("simulated truncated gzip at delete-stage verify")
        return original_verify(src, *args)
    monkeypatch.setattr(job, "_verify", corrupt_at_predelete)
    result = run(env, ["--enable-delete"], now + timedelta(hours=25))
    assert result == 1
    assert first.exists() and not second.exists()
    assert not any(record.exc_info for record in caplog.records)


@pytest.mark.parametrize("mode", ["--dry-run", "--report"])
def test_readonly_modes_do_not_adopt_legacy_manifest_or_write_state(env, mode):
    now = fixed_now(); path = add_file(env, now - timedelta(hours=4), mtime=(now - timedelta(hours=3)).timestamp())
    assert run(env, ["--no-delete"], now) == 0
    manifest = env[1] / path.relative_to(env[0]).parent.parent / "manifest.jsonl"
    legacy = [json.loads(line) for line in manifest.read_text().splitlines()]
    for record in legacy: record.pop("upload_id", None)
    manifest.write_text("".join(json.dumps(record) + "\n" for record in legacy))
    before = {str(p.relative_to(env[1])): p.read_bytes() for p in env[1].rglob("*") if p.is_file()}
    state = env[3].with_name("readonly-state")
    result = job.main(["--source", str(env[0]), "--dest", str(env[1]), "--mount", str(env[2]),
                       "--state-dir", str(state), mode], now=now + timedelta(minutes=1))
    assert result == 0
    after = {str(p.relative_to(env[1])): p.read_bytes() for p in env[1].rglob("*") if p.is_file()}
    assert after == before
    assert not state.exists()


def test_deletion_defers_when_hard_kill_grace_cannot_cover_next_file(env):
    now = fixed_now(); path = add_file(env, now - timedelta(days=9), mtime=(now - timedelta(days=8)).timestamp())
    assert run(env, ["--no-delete"], now) == 0
    result = job.main(["--source", str(env[0]), "--dest", str(env[1]), "--mount", str(env[2]),
                       "--state-dir", str(env[3]), "--enable-delete", "--hard-kill-grace-seconds", "1",
                       "--max-minutes", "0.2", "--throttle-mbps", "30", "--idle-seconds", "0"], now=now + timedelta(hours=25))
    assert result == 10
    assert path.exists()
    audit = env[1] / "deleted.jsonl"
    assert not audit.exists() or not any(json.loads(line)["phase"] == "intent" for line in audit.read_text().splitlines())


def test_restore_removes_duplicate_hardlink_tombstone(env):
    root, _, _, _ = env
    original = root / "2026/10/01/01/x.jsonl"
    original.parent.mkdir(parents=True); original.write_text("same")
    tomb = original.with_name(original.name + ".deleting-123")
    os.link(original, tomb)
    assert job._restore_tombstone(tomb, original)
    assert original.read_text() == "same" and not tomb.exists()


def test_near_deadline_defers_before_starting_delete_transaction(env, monkeypatch):
    now = fixed_now(); path = add_file(env, now - timedelta(days=9), mtime=(now - timedelta(days=8)).timestamp())
    assert run(env, ["--no-delete"], now) == 0
    observed = []
    monkeypatch.setattr(job, "_safe_delete", lambda *args, **kwargs: observed.append(args[0]))
    result = run(env, ["--enable-delete", "--hard-kill-grace-seconds", "1", "--max-minutes", "0.2"], now + timedelta(hours=25))
    assert observed == []
    assert result == 10
    assert path.exists()
    assert not (env[1] / "deleted.jsonl").exists()


def test_recreated_original_causes_day_to_be_retained(env, monkeypatch):
    now = fixed_now(); path = add_file(env, now - timedelta(days=9), mtime=(now - timedelta(days=8)).timestamp())
    assert run(env, ["--no-delete"], now) == 0
    original = job.Path.stat; created = [False]
    def recreate(tgt, *args, **kwargs):
        if ".deleting-" in tgt.name and not created[0]:
            created[0] = True
            path.write_bytes(b"new writer file")
            with tgt.open("ab") as stream: stream.write(b"late append")
        return original(tgt, *args, **kwargs)
    monkeypatch.setattr(job.Path, "stat", recreate)
    assert run(env, ["--enable-delete"], now + timedelta(hours=25)) != 0
    assert path.exists()


def test_idle_check_detects_change_during_wait(env, monkeypatch):
    now = fixed_now(); path = add_file(env, now - timedelta(days=9), mtime=(now - timedelta(days=8)).timestamp())
    assert run(env, ["--no-delete"], now) == 0
    real_sleep = job.time.sleep
    monkeypatch.setattr(job.time, "sleep", lambda _: path.write_bytes(path.read_bytes() + b"x"))
    assert run(env, ["--enable-delete", "--idle-seconds", "0.01"], now + timedelta(hours=25)) != 0
    assert path.exists()
    monkeypatch.setattr(job.time, "sleep", real_sleep)


def test_same_length_rewrite_with_restored_mtime_during_idle_is_not_deleted(env, monkeypatch):
    now = fixed_now(); path = add_file(env, now - timedelta(days=9), content=b"ORIGINAL", mtime=(now - timedelta(days=8)).timestamp())
    assert run(env, ["--no-delete"], now) == 0
    original_stat = path.stat()
    real_sleep = job.time.sleep
    def rewrite(_seconds):
        path.write_bytes(b"REPLACED")
        os.utime(path, ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns))
    monkeypatch.setattr(job.time, "sleep", rewrite)
    assert run(env, ["--enable-delete", "--idle-seconds", "0.01"], now + timedelta(hours=25)) != 0
    assert path.read_bytes() == b"REPLACED"
    monkeypatch.setattr(job.time, "sleep", real_sleep)


def test_same_length_tombstone_rewrite_after_rename_is_not_unlinked(env, monkeypatch):
    now = fixed_now(); path = add_file(env, now - timedelta(days=9), content=b"ORIGINAL", mtime=(now - timedelta(days=8)).timestamp())
    assert run(env, ["--no-delete"], now) == 0
    original_stat = job.Path.stat; changed = [False]
    def rewrite_tombstone(target, *args, **kwargs):
        if ".deleting-" in target.name and not changed[0]:
            changed[0] = True
            before = original_stat(target, *args, **kwargs)
            target.write_bytes(b"REPLACED")
            os.utime(target, ns=(before.st_atime_ns, before.st_mtime_ns))
        return original_stat(target, *args, **kwargs)
    monkeypatch.setattr(job.Path, "stat", rewrite_tombstone)
    assert run(env, ["--enable-delete"], now + timedelta(hours=25)) != 0
    assert path.exists() and path.read_bytes() == b"REPLACED"


def test_max_files_and_only_day_filter(env, caplog):
    caplog.set_level("INFO")
    now = fixed_now()
    add_file(env, now - timedelta(hours=4), "a.jsonl", mtime=(now - timedelta(hours=3)).timestamp())
    add_file(env, now - timedelta(hours=5), "b.jsonl", mtime=(now - timedelta(hours=3)).timestamp())
    add_file(env, now - timedelta(days=1, hours=4), "c.jsonl", mtime=(now - timedelta(days=1, hours=3)).timestamp())
    assert run(env, ["--dry-run", "--max-files", "1"], now) == 0
    assert sum("PLAN upload+verify" in rec.message for rec in caplog.records) == 1
    caplog.clear()
    day = (now - timedelta(days=1, hours=4)).strftime("%Y-%m-%d")
    assert run(env, ["--dry-run", "--only-day", day], now) == 0
    assert sum("PLAN upload+verify" in rec.message for rec in caplog.records) == 3


def test_dry_run_does_not_create_state_or_write_manifest(env):
    now = fixed_now(); path = add_file(env, now - timedelta(hours=4), mtime=(now - timedelta(hours=3)).timestamp())
    assert run(env, ["--no-delete"], now) == 0
    manifest = env[1] / path.relative_to(env[0]).parent.parent / "manifest.jsonl"
    manifest.write_text(manifest.read_text().replace('"type":"verified"', '"type":"invalid"'))
    before = manifest.read_bytes(); state = env[3]
    dry_state = env[3].with_name("absent-dry-state")
    assert job.main(["--source", str(env[0]), "--dest", str(env[1]), "--mount", str(env[2]), "--state-dir", str(dry_state), "--dry-run"], now=now + timedelta(minutes=1)) == 0
    assert manifest.read_bytes() == before
    assert not dry_state.exists()


def test_orphans_are_reported_read_only(env, capsys):
    now = fixed_now(); p = add_file(env, now - timedelta(hours=4), mtime=(now - timedelta(hours=3)).timestamp())
    orphan = p.with_name("lost.jsonl.deleting-1"); orphan.write_text("x")
    assert run(env, ["--report"], now) == 1
    report = json.loads(capsys.readouterr().out)
    assert str(orphan) in report["orphan_tombstones"]
    assert not (p.parent / "lost.jsonl").exists()


def test_report_does_not_count_legacy_upload_as_verified(env, capsys):
    now = fixed_now(); path = add_file(env, now - timedelta(hours=4), mtime=(now - timedelta(hours=3)).timestamp())
    assert run(env, ["--no-delete"], now) == 0
    manifest = env[1] / path.relative_to(env[0]).parent.parent / "manifest.jsonl"
    records = [json.loads(line) for line in manifest.read_text().splitlines()]
    for record in records: record.pop("upload_id", None)
    manifest.write_text("".join(json.dumps(record) + "\n" for record in records))
    assert run(env, ["--report"], now) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["uploaded"] == report["verified"] == 0


def test_report_flags_lone_delete_intent(env, capsys):
    add_file(env, fixed_now() - timedelta(hours=4), mtime=(fixed_now() - timedelta(hours=3)).timestamp())
    (env[1] / "deleted.jsonl").write_text('{"path":"x.jsonl","upload_id":"u","phase":"intent"}\n')
    assert run(env, ["--report"], fixed_now()) == 1
    assert json.loads(capsys.readouterr().out)["dangling_intents"] == ["x.jsonl"]


def test_max_files_skips_recently_failed_file_to_process_later(env, monkeypatch):
    now = fixed_now()
    first = add_file(env, now - timedelta(hours=5), "a.jsonl", mtime=(now - timedelta(hours=3)).timestamp())
    second = add_file(env, now - timedelta(hours=4), "b.jsonl", mtime=(now - timedelta(hours=3)).timestamp())
    original = job._copy_gzip
    def fail_first(src, *args, **kwargs):
        if src == first: raise OSError("temporary write failure")
        return original(src, *args, **kwargs)
    monkeypatch.setattr(job, "_copy_gzip", fail_first)
    assert run(env, ["--no-delete", "--max-files", "1"], now) == 1
    monkeypatch.setattr(job, "_copy_gzip", original)
    # A capped partial UTC day cannot pass the new full-day completeness barrier.
    assert run(env, ["--no-delete", "--max-files", "1"], now + timedelta(seconds=30)) != 0
    assert (env[1] / second.relative_to(env[0]).parent / (second.name + ".gz")).exists()
    assert not (env[1] / first.relative_to(env[0]).parent / (first.name + ".gz")).exists()


def test_changed_source_during_final_check_is_retained(env, monkeypatch):
    now = fixed_now(); path = add_file(env, now - timedelta(days=9), mtime=(now - timedelta(days=8)).timestamp())
    run(env, now=now - timedelta(hours=30))
    original_stat = job.Path.stat; changed = [False]
    def race_stat(p, *args, **kwargs):
        if ".deleting-" in p.name and not changed[0]:
            changed[0] = True
            with p.open("ab") as stream: stream.write(b"late append")
        return original_stat(p, *args, **kwargs)
    monkeypatch.setattr(job.Path, "stat", race_stat)
    assert run(env, ["--enable-delete"], now=now + timedelta(hours=25)) != 0
    assert path.exists()


@pytest.mark.parametrize("missing_id", [True, False])
def test_old_manifest_grace_cannot_substitute_for_fresh_day_completion(env, missing_id):
    now = fixed_now(); path = add_file(env, now - timedelta(days=9), mtime=(now - timedelta(days=8)).timestamp())
    assert run(env, now=now) == 0
    manifest = env[1] / path.relative_to(env[0]).parent.parent / "manifest.jsonl"
    records = [json.loads(x) for x in manifest.read_text().splitlines()]
    if missing_id:
        for record in records: record.pop("upload_id", None)
    manifest.write_text("\n".join(json.dumps(r) for r in records) + "\n")
    assert run(env, ["--enable-delete"], now=now + timedelta(days=4)) == 0
    assert not path.exists()


def test_watchdog_calls_callback():
    called = []
    beat, stop, thread = job._watchdog(.15, callback=called.append)
    thread.join(1); stop.set()
    assert called == [3]


def test_deadline_stops_after_slow_mount_stage(env, monkeypatch):
    root, dest, mount, state = env
    entered = []
    def slow_mount(*args):
        entered.append(True)
        time.sleep(.05)
        return True
    monkeypatch.setattr(job, "_ensure_mounted", slow_mount)
    monkeypatch.setattr(job, "_preflight", lambda *args: pytest.fail("preflight ran after deadline"))
    result = job.main(["--source", str(root), "--dest", str(dest), "--mount", str(mount),
                       "--state-dir", str(state), "--max-minutes", "0.0001",
                       "--io-timeout", "10"], now=fixed_now())
    assert result == 10
    assert entered


def test_hard_deadline_kills_blocked_mount_and_releases_lock(env):
    root, dest, mount, state = env
    state.mkdir(parents=True)
    code = (
        "import importlib.util,time; from pathlib import Path; "
        f"p=Path({str(SCRIPT)!r}); s=importlib.util.spec_from_file_location('archive_to_nas_child',p); "
        "m=importlib.util.module_from_spec(s); s.loader.exec_module(m); "
        "m.MOUNT_CHECK=lambda *a: (time.sleep(10) or True); "
        f"raise SystemExit(m.main(['--source',{str(root)!r},'--dest',{str(dest)!r},'--mount',{str(mount)!r},"
        f"'--state-dir',{str(state)!r},'--max-minutes','0.001','--io-timeout','10',"
        "'--hard-kill-grace-seconds','0.2']))"
    )
    completed = subprocess.run([os.environ.get("PYTHON", "/opt/anaconda3/bin/python3"), "-c", code],
                               capture_output=True, text=True, timeout=5)
    assert completed.returncode == 3, completed.stderr
    with (state / "archive_to_nas.lock").open("a+") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def test_status_reports_stale_live_process(tmp_path, capsys, monkeypatch):
    state = tmp_path / "state"; state.mkdir()
    (state / "archive_to_nas.status.json").write_text(json.dumps({
        "pid": os.getpid(), "stage": "scanning NAS", "started_epoch": time.time() - 700,
        "last_progress_epoch": time.time() - 700,
    }))
    assert job.main(["--status", "--state-dir", str(state)]) == 1
    assert json.loads(capsys.readouterr().out)["stage"] == "scanning NAS"


def test_run_emits_start_progress_and_summary(env, caplog):
    caplog.set_level("INFO")
    assert run(env, ["--no-delete"], fixed_now()) == 0
    messages = [record.getMessage() for record in caplog.records]
    assert any(message.startswith("start pid=") for message in messages)
    assert any("stage=starting" in message for message in messages)
    assert any(message.startswith("summary ") for message in messages)


def test_transient_verify_error_blocks_same_run_completion_and_delete(env, monkeypatch):
    now = fixed_now(); path = add_file(env, now - timedelta(days=9), mtime=(now - timedelta(days=8)).timestamp())
    original = job._verify
    assert run(env, now=now) == 0
    manifest = env[1] / path.relative_to(env[0]).parent.parent / "manifest.jsonl"
    monkeypatch.setattr(job, "_verify", lambda *a, **k: (_ for _ in ()).throw(OSError("temporary NAS read error")))
    assert run(env, ["--enable-delete"], now=now + timedelta(hours=1)) == 1
    assert path.exists()
    assert not any(r.get("type") == "invalid" for r in map(json.loads, manifest.read_text().splitlines()))
    monkeypatch.setattr(job, "_verify", original)


def test_mount_loss_mid_run_aborts_before_next_file(env, monkeypatch):
    now = fixed_now()
    first = add_file(env, now - timedelta(hours=4), "one.jsonl", mtime=(now - timedelta(hours=3)).timestamp())
    second = add_file(env, now - timedelta(hours=4), "two.jsonl", mtime=(now - timedelta(hours=3)).timestamp())
    calls = [0]
    def mount(mount, dest, root):
        calls[0] += 1
        return calls[0] < 5
    monkeypatch.setattr(job, "MOUNT_CHECK", mount)
    assert run(env, now=now) == 2
    assert first.exists() and second.exists()
    assert not (env[1] / second.relative_to(env[0])).exists()


def test_symlink_skipped(env):
    now = fixed_now(); target = add_file(env, now - timedelta(hours=4), mtime=(now - timedelta(hours=3)).timestamp())
    link = target.with_name("linked.jsonl"); link.symlink_to(target)
    assert all(candidate[1] != link for candidate in job._scan(env[0], now))


def test_truncated_manifest_healed(tmp_path):
    path = tmp_path / "manifest.jsonl"; path.write_bytes(b'{"old":1}')
    job._json_append(path, {"new": 2})
    assert len(path.read_text().splitlines()) == 2


def test_old_part_sweep_and_disk_usage_failure(env, monkeypatch):
    now = fixed_now(); path = add_file(env, now - timedelta(hours=4), mtime=(now - timedelta(hours=3)).timestamp())
    part = env[1] / path.relative_to(env[0]).parent / "orphan.part"
    part.parent.mkdir(parents=True, exist_ok=True); part.write_text("x"); os.utime(part, (time.time()-90000,)*2)
    assert run(env, now=now) == 0
    assert not part.exists()
    monkeypatch.setattr(job.shutil, "disk_usage", lambda p: (_ for _ in ()).throw(OSError("gone")))
    assert run(env, now=now) == 2


def test_plist_is_safe_default():
    plist = SCRIPT.parents[1] / "docs/launchd/com.ochestration.archive-to-nas.plist.template"
    text = plist.read_text()
    assert "--max-minutes" in text and "--no-delete" in text and "--enable-delete" not in text


def test_dangling_delete_intent_is_reconciled_as_abort_when_source_exists(env):
    now = fixed_now(); path = add_file(env, now - timedelta(days=9), mtime=(now - timedelta(days=8)).timestamp())
    audit = env[1] / "deleted.jsonl"
    audit.write_text(json.dumps({"path": path.relative_to(env[0]).as_posix(), "upload_id": "interrupted", "phase": "intent"}) + "\n")
    assert run(env, ["--no-delete"], now) == 0
    records = [json.loads(row) for row in audit.read_text().splitlines()]
    assert records[-1]["phase"] == "abort"
    assert path.exists()


def test_orphan_deleting_tombstone_is_restored_without_permanent_failure(env):
    now = fixed_now(); path = add_file(env, now - timedelta(days=9), mtime=(now - timedelta(days=8)).timestamp())
    tomb = path.with_name(path.name + ".deleting-12345")
    path.rename(tomb)
    assert run(env, ["--no-delete"], now) == 0
    assert path.exists() and not tomb.exists()


def test_tombstone_recovery_collision_preserves_new_source_and_late_tombstone(env, monkeypatch):
    now = fixed_now(); path = add_file(env, now - timedelta(days=9), content=b"old", mtime=(now - timedelta(days=8)).timestamp())
    tomb = path.with_name(path.name + ".deleting-12345")
    path.rename(tomb)
    real_link = job.os.link; injected = [False]
    def race_link(source, target, *args, **kwargs):
        if Path(target) == path and not injected[0]:
            injected[0] = True
            path.write_bytes(b"new writer bytes")
        return real_link(source, target, *args, **kwargs)
    monkeypatch.setattr(job.os, "link", race_link)
    assert run(env, ["--no-delete"], now) == 0
    assert path.read_bytes() == b"new writer bytes"
    late = list(path.parent.glob(path.name + ".deleting-*.late-*"))
    assert len(late) == 1 and late[0].read_bytes() == b"old"


def test_dangling_intent_recovery_collision_is_non_clobbering(env, monkeypatch):
    now = fixed_now(); path = add_file(env, now - timedelta(days=9), content=b"old", mtime=(now - timedelta(days=8)).timestamp())
    tomb = path.with_name(path.name + ".deleting-12345")
    path.rename(tomb)
    audit = env[1] / "deleted.jsonl"
    audit.write_text(json.dumps({"path": path.relative_to(env[0]).as_posix(), "upload_id": "interrupted", "phase": "intent"}) + "\n")
    real_restore = job._restore_tombstone; calls = [0]
    def inject_on_dangling_restore(source, target):
        calls[0] += 1
        if calls[0] == 1:
            raise OSError("injected recovery deferral")
        path.write_bytes(b"concurrent writer")
        return real_restore(source, target)
    monkeypatch.setattr(job, "_restore_tombstone", inject_on_dangling_restore)
    assert run(env, ["--no-delete"], now) == 0
    assert path.read_bytes() == b"concurrent writer"
    late = list(path.parent.glob(path.name + ".deleting-*.late-*"))
    assert len(late) == 1 and late[0].read_bytes() == b"old"


def test_archive_deadline_returns_partial_status_10(env, monkeypatch):
    now = fixed_now(); add_file(env, now - timedelta(days=9), mtime=(now - timedelta(days=8)).timestamp())
    assert run(env, ["--no-delete", "--max-minutes", "0.000001"], now) == 10


def test_invalid_only_day_returns_argument_error_without_traceback(env, caplog):
    assert run(env, ["--only-day", "yesterday"], fixed_now()) == 2
    assert "--only-day must use YYYY-MM-DD" in caplog.text


def test_deletion_idle_wait_occurs_once_per_day(env, monkeypatch):
    now = fixed_now()
    first = add_file(env, now - timedelta(days=9), "a.jsonl", mtime=(now - timedelta(days=8)).timestamp())
    add_file(env, now - timedelta(days=9), "b.jsonl", mtime=(now - timedelta(days=8)).timestamp())
    calls = []
    monkeypatch.setattr(job.time, "sleep", lambda seconds: calls.append(seconds))
    assert run(env, ["--enable-delete", "--idle-seconds", "5"], now) == 0
    assert calls.count(5) == 1
    assert not first.exists()


def test_early_return_does_not_leak_hard_kill_watchers(env):
    """Regression: early returns after arming left daemon watchers that later os._exit(3) the whole pytest process."""
    import threading
    root, dest, mount, state = env
    before = set(threading.enumerate())
    result = job.main(["--source", str(root / "missing"), "--dest", str(dest), "--mount", str(mount),
                       "--state-dir", str(state), "--hard-kill-grace-seconds", "0.2", "--max-minutes", "0.001"])
    assert result == 2
    time.sleep(1.5)
    assert not [t for t in threading.enumerate() if t not in before and t.is_alive()]
