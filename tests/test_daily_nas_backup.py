import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NO_TICK = ROOT / "scripts/backup-tick-archive-to-nas.sh"
WRAPPER = ROOT / "scripts/daily_nas_backup.sh"


def executable(path, content):
    path.write_text(content)
    path.chmod(0o755)


def test_backup_script_bash_syntax():
    subprocess.run(["/bin/bash", "-n", str(NO_TICK)], check=True)
    subprocess.run(["/bin/bash", "-n", str(WRAPPER)], check=True)


def test_state_db_dispatch_never_deletes_tick_archive_or_bypasses_timeout(tmp_path):
    project = tmp_path / "project"
    tick = project / "trading-tick-archive/2026/11/01"
    tick.mkdir(parents=True)
    (tick / "local.jsonl").write_text("keep")
    for folder in ("trading-crypto-paper-state", "backups"):
        (project / folder).mkdir(parents=True)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    calls = tmp_path / "calls.log"
    timeouts = tmp_path / "timeouts.log"
    executable(bin_dir / "mount", f"#!/bin/sh\necho 'server on {tmp_path}/nas (smbfs)'\n")
    executable(bin_dir / "docker", f"#!/bin/sh\necho \"docker:$*\" >> '{calls}'\nif [ \"$1\" = ps ]; then printf '%s\\n' ochestration-trading-trading-momentum-rotation-1 ochestration-trading-trading-kr-rotation-1 ochestration-trading-trading-us-rotation-1; fi\nif [ \"$1\" = cp ]; then mkdir -p \"$3\"; echo '{{}}' > \"$3/state.json\"; fi\n")
    executable(bin_dir / "rsync", f"#!/bin/sh\necho \"rsync:$*\" >> '{calls}'\n")
    executable(bin_dir / "perl", f"#!/bin/sh\necho \"$4\" >> '{timeouts}'\nexec /usr/bin/perl \"$@\"\n")
    env = os.environ | {
        "PATH": f"{bin_dir}:/usr/bin:/bin:/usr/sbin:/sbin",
        "PROJECT_ROOT": str(project), "MOUNT_POINT": str(tmp_path / "nas"),
        "BACKUP_LOG_FILE": str(tmp_path / "backup.log"),
        "DOCKER_BIN": str(bin_dir / "docker"), "RSYNC_BIN": str(bin_dir / "rsync"),
        "PERL_BIN": str(bin_dir / "perl"), "MOUNT_BIN": str(bin_dir / "mount"),
    }
    result = subprocess.run(["/bin/bash", str(NO_TICK), "state-db-only"], env=env, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    assert tick.exists() and (tick / "local.jsonl").read_text() == "keep"
    recorded = calls.read_text()
    assert "docker:ps" in recorded and "docker:cp" in recorded and "rsync:" in recorded
    assert {"300", "1800"}.issubset(set(timeouts.read_text().splitlines()))
    assert "backup_tick_archive" not in (tmp_path / "backup.log").read_text()


def test_wrapper_aggregates_state_db_and_archive_failures(tmp_path):
    project = tmp_path / "project"
    scripts = project / "scripts"
    scripts.mkdir(parents=True)
    tick = scripts / "tick.sh"
    archive = scripts / "archive.py"
    executable(tick, "#!/bin/sh\nexit 7\n")
    executable(archive, "#!/bin/sh\necho archive-ran >> \"$ARCHIVE_MARKER\"\nexit 9\n")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    executable(bin_dir / "mount", f"#!/bin/sh\necho 'server on {tmp_path}/nas (smbfs)'\n")
    marker = tmp_path / "archive.marker"
    env = os.environ | {
        "PROJECT_ROOT": str(project), "TICK_BACKUP_SCRIPT": str(tick),
        "ARCHIVE_SCRIPT": str(archive), "PYTHON_BIN": "/bin/sh",
        "MOUNT_BIN": str(bin_dir / "mount"), "MOUNT_POINT": str(tmp_path / "nas"),
        "STATE_DIR": str(tmp_path / "state"), "DAILY_BACKUP_LOG": str(tmp_path / "daily.log"),
        "ARCHIVE_MARKER": str(marker),
    }
    result = subprocess.run(["/bin/bash", str(WRAPPER)], env=env, text=True, capture_output=True)
    assert result.returncode == 1
    assert marker.read_text().strip() == "archive-ran"
    log = (tmp_path / "daily.log").read_text()
    assert "state/DB backup failed" in log and "archive uploader failed" in log
    assert "DAILY NAS BACKUP FAILURE" in log
    assert not (tmp_path / "state/daily_nas_backup.last_success").exists()


def test_wrapper_rejects_modes_and_backup_script_rejects_legacy_modes(tmp_path):
    project = tmp_path / "project"
    tick = project / "trading-tick-archive/2026/11/01"
    tick.mkdir(parents=True)
    (tick / "a.jsonl").write_text("keep")
    bin_dir = tmp_path / "bin"; bin_dir.mkdir()
    executable(bin_dir / "mount", f"#!/bin/sh\necho 'server on {tmp_path}/nas (smbfs)'\n")
    env = os.environ | {"PROJECT_ROOT": str(project), "MOUNT_POINT": str(tmp_path / "nas"),
                        "BACKUP_LOG_FILE": str(tmp_path / "backup.log"), "MOUNT_BIN": str(bin_dir / "mount")}
    for args in (["all"], ["tick-only"], ["no-tick"]):
        result = subprocess.run(["/bin/bash", str(NO_TICK), *args], env=env, capture_output=True, text=True)
        assert result.returncode == 2
        assert (tick / "a.jsonl").read_text() == "keep"
    result = subprocess.run(["/bin/bash", str(WRAPPER), "no-tick"], env=env, capture_output=True, text=True)
    assert result.returncode == 2


def test_wrapper_defaults_no_delete_and_records_success_per_step(tmp_path):
    project = tmp_path / "project"; scripts = project / "scripts"; scripts.mkdir(parents=True)
    tick = scripts / "tick.sh"; executable(tick, "#!/bin/sh\nexit 0\n")
    archive = scripts / "archive.py"
    executable(archive, "#!/bin/sh\nprintf '%s\\n' \"$@\" > \"$ARCHIVE_ARGS\"\nexit 0\n")
    bin_dir = tmp_path / "bin"; bin_dir.mkdir()
    executable(bin_dir / "mount", f"#!/bin/sh\necho 'server on {tmp_path}/nas (smbfs)'\n")
    state = tmp_path / "state"
    env = os.environ | {"PROJECT_ROOT": str(project), "TICK_BACKUP_SCRIPT": str(tick), "ARCHIVE_SCRIPT": str(archive),
                        "PYTHON_BIN": "/bin/sh", "MOUNT_BIN": str(bin_dir / "mount"), "MOUNT_POINT": str(tmp_path / "nas"),
                        "STATE_DIR": str(state), "DAILY_BACKUP_LOG": str(tmp_path / "daily.log"),
                        "ARCHIVE_ARGS": str(tmp_path / "args")}
    result = subprocess.run(["/bin/bash", str(WRAPPER)], env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    args = (tmp_path / "args").read_text().splitlines()
    assert "--no-delete" in args and "--enable-delete" not in args
    assert (state / "daily_nas_backup.last_success.state-db").exists()
    assert (state / "daily_nas_backup.last_success.archive").exists()


def test_wrapper_exit_10_records_partial_without_success_marker(tmp_path):
    project = tmp_path / "project"; scripts = project / "scripts"; scripts.mkdir(parents=True)
    tick = scripts / "tick.sh"; executable(tick, "#!/bin/sh\nexit 0\n")
    archive = scripts / "archive.py"; executable(archive, "#!/bin/sh\nexit 10\n")
    bin_dir = tmp_path / "bin"; bin_dir.mkdir(); executable(bin_dir / "mount", f"#!/bin/sh\necho 'server on {tmp_path}/nas (smbfs)'\n")
    state = tmp_path / "state"; state.mkdir(); (state / "daily_nas_backup.last_success.archive").write_text("stale")
    env = os.environ | {"PROJECT_ROOT": str(project), "TICK_BACKUP_SCRIPT": str(tick), "ARCHIVE_SCRIPT": str(archive),
        "PYTHON_BIN": "/bin/sh", "MOUNT_BIN": str(bin_dir / "mount"), "MOUNT_POINT": str(tmp_path / "nas"),
        "STATE_DIR": str(state), "DAILY_BACKUP_LOG": str(tmp_path / "daily.log")}
    result = subprocess.run(["/bin/bash", str(WRAPPER)], env=env, capture_output=True, text=True)
    assert result.returncode == 10
    assert not (state / "daily_nas_backup.last_success.archive").exists()
    assert (state / "daily_nas_backup.last_partial.archive").exists()
    assert not (state / "daily_nas_backup.last_success").exists()


def test_state_db_failure_dominates_archive_deferred_and_clears_stale_markers(tmp_path):
    project = tmp_path / "project"; scripts = project / "scripts"; scripts.mkdir(parents=True)
    tick = scripts / "tick.sh"; executable(tick, "#!/bin/sh\nexit 7\n")
    archive = scripts / "archive.py"; executable(archive, "#!/bin/sh\nexit 10\n")
    bin_dir = tmp_path / "bin"; bin_dir.mkdir(); executable(bin_dir / "mount", f"#!/bin/sh\necho 'server on {tmp_path}/nas (smbfs)'\n")
    state = tmp_path / "state"; state.mkdir()
    for marker in ("state-db", "archive"):
        (state / f"daily_nas_backup.last_success.{marker}").write_text("stale")
    env = os.environ | {"PROJECT_ROOT": str(project), "TICK_BACKUP_SCRIPT": str(tick), "ARCHIVE_SCRIPT": str(archive),
        "PYTHON_BIN": "/bin/sh", "MOUNT_BIN": str(bin_dir / "mount"), "MOUNT_POINT": str(tmp_path / "nas"),
        "STATE_DIR": str(state), "DAILY_BACKUP_LOG": str(tmp_path / "daily.log")}
    result = subprocess.run(["/bin/bash", str(WRAPPER)], env=env, capture_output=True, text=True)
    assert result.returncode == 1
    assert not (state / "daily_nas_backup.last_success.state-db").exists()
    assert not (state / "daily_nas_backup.last_success.archive").exists()
    assert not (state / "daily_nas_backup.last_success").exists()


def test_wrapper_rejects_mode_arguments(tmp_path):
    project = tmp_path / "project"; scripts = project / "scripts"; scripts.mkdir(parents=True)
    tick = scripts / "tick.sh"; executable(tick, "#!/bin/sh\nexit 0\n")
    archive = scripts / "archive.py"; executable(archive, "#!/bin/sh\necho called >> \"$ARCHIVE_MARKER\"\nexit 0\n")
    bin_dir = tmp_path / "bin"; bin_dir.mkdir(); executable(bin_dir / "mount", f"#!/bin/sh\necho 'server on {tmp_path}/nas (smbfs)'\n")
    marker = tmp_path / "archive.marker"
    env = os.environ | {"PROJECT_ROOT": str(project), "TICK_BACKUP_SCRIPT": str(tick), "ARCHIVE_SCRIPT": str(archive),
        "PYTHON_BIN": "/bin/sh", "MOUNT_BIN": str(bin_dir / "mount"), "MOUNT_POINT": str(tmp_path / "nas"),
        "STATE_DIR": str(tmp_path / "state"), "DAILY_BACKUP_LOG": str(tmp_path / "daily.log"), "ARCHIVE_MARKER": str(marker)}
    result = subprocess.run(["/bin/bash", str(WRAPPER), "--only", "no-tick"], env=env, capture_output=True, text=True)
    assert result.returncode == 2
    assert not marker.exists()


def test_wrapper_mount_retry_deadline_bounds_mount_command(tmp_path):
    project = tmp_path / "project"; project.mkdir()
    bin_dir = tmp_path / "bin"; bin_dir.mkdir()
    executable(bin_dir / "mount", "#!/bin/sh\nexec /bin/sleep 20\n")
    env = os.environ | {"PROJECT_ROOT": str(project), "MOUNT_BIN": str(bin_dir / "mount"),
        "OPEN_BIN": "/bin/true", "MOUNT_POINT": str(tmp_path / "nas"), "STATE_DIR": str(tmp_path / "state"),
        "DAILY_BACKUP_LOG": str(tmp_path / "daily.log"), "NAS_RETRY_WINDOW_SECONDS": "2", "TIMEOUT_GRACE_SECONDS": "0"}
    started = __import__("time").monotonic()
    result = subprocess.run(["/bin/bash", str(WRAPPER)], env=env, capture_output=True, text=True, timeout=6)
    elapsed = __import__("time").monotonic() - started
    assert result.returncode == 1
    assert elapsed < 4
    assert "NAS mount unavailable" in (tmp_path / "daily.log").read_text()


def test_wrapper_delete_requires_explicit_environment_flag(tmp_path):
    project = tmp_path / "project"; scripts = project / "scripts"; scripts.mkdir(parents=True)
    tick = scripts / "tick.sh"; executable(tick, "#!/bin/sh\nexit 0\n")
    archive = scripts / "archive.py"; executable(archive, "#!/bin/sh\nprintf '%s\\n' \"$@\" > \"$ARCHIVE_ARGS\"\nexit 0\n")
    bin_dir = tmp_path / "bin"; bin_dir.mkdir(); executable(bin_dir / "mount", f"#!/bin/sh\necho 'server on {tmp_path}/nas (smbfs)'\n")
    env = os.environ | {"PROJECT_ROOT": str(project), "TICK_BACKUP_SCRIPT": str(tick), "ARCHIVE_SCRIPT": str(archive),
        "PYTHON_BIN": "/bin/sh", "MOUNT_BIN": str(bin_dir / "mount"), "MOUNT_POINT": str(tmp_path / "nas"),
        "STATE_DIR": str(tmp_path / "state"), "DAILY_BACKUP_LOG": str(tmp_path / "daily.log"),
        "ARCHIVE_ARGS": str(tmp_path / "args"), "DAILY_NAS_ENABLE_DELETE": "1"}
    subprocess.run(["/bin/bash", str(WRAPPER)], env=env, check=True, capture_output=True)
    args = (tmp_path / "args").read_text().splitlines()
    assert "--enable-delete" in args and "--no-delete" not in args


def test_docker_ps_failure_is_not_reported_as_missing_container_success(tmp_path):
    project = tmp_path / "project"; project.mkdir()
    bin_dir = tmp_path / "bin"; bin_dir.mkdir()
    executable(bin_dir / "mount", f"#!/bin/sh\necho 'server on {tmp_path}/nas (smbfs)'\n")
    executable(bin_dir / "docker", "#!/bin/sh\nexit 42\n")
    executable(bin_dir / "rsync", "#!/bin/sh\nexit 0\n")
    env = os.environ | {"PROJECT_ROOT": str(project), "MOUNT_POINT": str(tmp_path / "nas"),
        "BACKUP_LOG_FILE": str(tmp_path / "backup.log"), "MOUNT_BIN": str(bin_dir / "mount"),
        "DOCKER_BIN": str(bin_dir / "docker"), "RSYNC_BIN": str(bin_dir / "rsync"),
        "PERL_BIN": "/usr/bin/perl"}
    result = subprocess.run(["/bin/bash", str(NO_TICK), "state-db-only"], env=env, capture_output=True, text=True)
    assert result.returncode == 1
    assert "docker ps 실패" in (tmp_path / "backup.log").read_text()


def test_daily_plist_defaults_delete_off():
    plist = WRAPPER.parents[1] / "trading/docs/launchd/com.ochestration.daily-nas-backup.plist.template"
    text = plist.read_text()
    assert "DAILY_NAS_ENABLE_DELETE" in text and "<string>0</string>" in text


def test_wrapper_reclaims_dead_stale_lock(tmp_path):
    project = tmp_path / "project"; scripts = project / "scripts"; scripts.mkdir(parents=True)
    tick = scripts / "tick.sh"; executable(tick, "#!/bin/sh\nexit 0\n")
    archive = scripts / "archive.py"; executable(archive, "#!/bin/sh\nexit 0\n")
    bin_dir = tmp_path / "bin"; bin_dir.mkdir(); executable(bin_dir / "mount", f"#!/bin/sh\necho 'server on {tmp_path}/nas (smbfs)'\n")
    state = tmp_path / "state"; lock = state / "daily_nas_backup.lock"; lock.mkdir(parents=True); (lock / "pid").write_text("99999999\n")
    env = os.environ | {"PROJECT_ROOT": str(project), "TICK_BACKUP_SCRIPT": str(tick), "ARCHIVE_SCRIPT": str(archive),
        "PYTHON_BIN": "/bin/sh", "MOUNT_BIN": str(bin_dir / "mount"), "MOUNT_POINT": str(tmp_path / "nas"),
        "STATE_DIR": str(state), "DAILY_BACKUP_LOG": str(tmp_path / "daily.log"), "STALE_AFTER_SECONDS": "0"}
    result = subprocess.run(["/bin/bash", str(WRAPPER)], env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert not lock.exists()
