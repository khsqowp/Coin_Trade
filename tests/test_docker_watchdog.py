import subprocess
import time
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "docker_watchdog.sh"


def _executable(path: Path, body: str) -> Path:
    path.write_text("#!/bin/bash\n" + body, encoding="utf-8")
    path.chmod(0o755)
    return path


@pytest.fixture
def watchdog(tmp_path):
    bindir = tmp_path / "bin"
    bindir.mkdir()
    state = tmp_path / "state"
    state.mkdir()
    calls = tmp_path / "docker-info-count"
    docker = _executable(
        bindir / "docker",
        """case "$1" in
  info)
    count=0; [[ -f "$DOCKER_INFO_COUNT" ]] && read -r count < "$DOCKER_INFO_COUNT"
    count=$((count + 1)); printf '%s\\n' "$count" > "$DOCKER_INFO_COUNT"
    if [[ ${ENGINE_MODE:-ok} == fail || ( ${ENGINE_MODE:-ok} == fail3 && $count -le 3 ) ]]; then exit 1; fi
    exit 0 ;;
  inspect) printf '%s\\n' "${INSPECT_VALUE:-0 false true}" ;;
  exec) printf 'MISSING 1000\\n' ;;
  *) exit 2 ;;
esac
""",
    )
    actions = tmp_path / "actions.log"
    osascript = _executable(bindir / "osascript", 'printf "%s\\n" "$*" >> "$ACTION_LOG"\n')
    open_app = _executable(bindir / "open", 'printf "open %s\\n" "$*" >> "$ACTION_LOG"\n')
    # Mirrors macOS process names: the app is reported as "Docker Desktop".
    pgrep = _executable(
        bindir / "pgrep",
        """count=0; [[ -f "$PGREP_COUNT" ]] && read -r count < "$PGREP_COUNT"
count=$((count + 1)); printf '%s\\n' "$count" > "$PGREP_COUNT"
[[ $count -le ${PGREP_GONE_AFTER:-999999} ]] && { printf 'Docker Desktop\\n'; exit 0; }
exit 1
""",
    )
    sleep = _executable(bindir / "sleep", "exit 0\n")
    perl = _executable(bindir / "perl", 'exec /usr/bin/perl "$@"\n')
    date = _executable(bindir / "date", 'exec /bin/date "$@"\n')
    sysctl = _executable(
        bindir / "sysctl",
        'printf "vm.swapusage: total = 18.00G used = ${SWAP_USED:-1.00G} free = 1.00G\\n"\n',
    )
    base = {
        "HOME": str(tmp_path), "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
        "WATCHDOG_STATE_DIR": str(state), "WATCHDOG_DOCKER_BIN": str(docker),
        "WATCHDOG_OSASCRIPT_BIN": str(osascript), "WATCHDOG_OPEN_BIN": str(open_app),
        "WATCHDOG_PGREP_BIN": str(pgrep), "WATCHDOG_SLEEP_BIN": str(sleep),
        "WATCHDOG_PERL_BIN": str(perl), "WATCHDOG_DATE_BIN": str(date),
        "WATCHDOG_SYSCTL_BIN": str(sysctl), "DOCKER_INFO_COUNT": str(calls),
        "PGREP_COUNT": str(tmp_path / "pgrep-count"), "ACTION_LOG": str(actions),
    }

    def run(*args, **extra):
        env = {**base, **extra}
        return subprocess.run(
            ["/bin/bash", str(SCRIPT), "--check-once", *args], env=env,
            text=True, capture_output=True, timeout=10, check=False,
        )

    return state, actions, calls, base, run


def test_engine_dead_three_spaced_failures_restart_after_desktop_exits(watchdog):
    state, actions, _, _, run = watchdog
    for now in (1800000000, 1800000180, 1800000360):
        assert run(ENGINE_MODE="fail3", WATCHDOG_NOW_EPOCH=str(now), PGREP_GONE_AFTER="3").returncode == 0
    log = (state / "watchdog.log").read_text()
    calls = actions.read_text()
    assert "ACTION restarting Docker Desktop" in log
    assert "OK Docker engine returned" in log
    assert len((state / "restart_epochs").read_text().splitlines()) == 1
    assert "quit app" in calls and "open -a Docker" in calls
    assert calls.index("quit app") < calls.index("open -a Docker")


def test_expired_failure_streak_does_not_restart(watchdog):
    state, actions, _, _, run = watchdog
    now = 1800000000
    (state / "engine_failure_count").write_text("2\n")
    (state / "engine_failure_since_epoch").write_text(f"{now - 1000}\n")
    (state / "last_run_epoch").write_text(f"{now - 1000}\n")
    assert run(ENGINE_MODE="fail", WATCHDOG_NOW_EPOCH=str(now)).returncode == 0
    assert "WAKE grace" in (state / "watchdog.log").read_text()
    assert not actions.exists() or "quit app" not in actions.read_text()
    assert (state / "engine_failure_count").read_text().strip() == "0"


def test_failure_streak_older_than_15_minutes_expires(watchdog):
    state, actions, _, _, run = watchdog
    now = 1800000000
    (state / "engine_failure_count").write_text("2\n")
    (state / "engine_failure_since_epoch").write_text(f"{now - 901}\n")
    (state / "last_run_epoch").write_text(f"{now - 120}\n")
    assert run(ENGINE_MODE="fail", WATCHDOG_NOW_EPOCH=str(now)).returncode == 0
    assert "consecutive=1" in (state / "watchdog.log").read_text()
    assert not actions.exists() or "quit app" not in actions.read_text()


def test_wake_gap_resets_and_skips_one_cycle(watchdog):
    state, actions, calls, _, run = watchdog
    now = 1800000000
    (state / "engine_failure_count").write_text("2\n")
    (state / "engine_failure_since_epoch").write_text(f"{now - 361}\n")
    (state / "last_run_epoch").write_text(f"{now - 361}\n")
    assert run(ENGINE_MODE="fail", WATCHDOG_NOW_EPOCH=str(now)).returncode == 0
    assert "WAKE grace cycle skipped" in (state / "watchdog.log").read_text()
    assert not calls.exists()
    assert not actions.exists() or "quit app" not in actions.read_text()


def test_app_not_running_is_alert_only(watchdog):
    state, actions, _, _, run = watchdog
    for now in (1800000000, 1800000180, 1800000360):
        run(ENGINE_MODE="fail", WATCHDOG_NOW_EPOCH=str(now), PGREP_GONE_AFTER="0")
    assert "app is not running" in (state / "watchdog.log").read_text()
    assert "quit app" not in actions.read_text()
    assert "open -a Docker" not in actions.read_text()


def test_pause_prevents_engine_restart(watchdog):
    state, actions, _, _, run = watchdog
    (state / "PAUSE").touch()
    for now in (1800000000, 1800000180, 1800000360):
        run(ENGINE_MODE="fail", WATCHDOG_NOW_EPOCH=str(now))
    assert "PAUSE file present" in (state / "watchdog.log").read_text()
    assert "quit app" not in actions.read_text()


def test_quit_not_exited_consumes_attempt_and_never_reopens(watchdog):
    state, actions, _, _, run = watchdog
    for now in (1800000000, 1800000180, 1800000360):
        run(ENGINE_MODE="fail", WATCHDOG_NOW_EPOCH=str(now), PGREP_GONE_AFTER="999999")
    assert "did not exit within 60s" in (state / "watchdog.log").read_text()
    assert "quit app" in actions.read_text()
    assert "open -a Docker" not in actions.read_text()
    assert (state / "last_restart_epoch").read_text().strip() == "1800000360"
    assert len((state / "restart_epochs").read_text().splitlines()) == 1


def test_swap_alert_uses_relative_threshold_and_six_hour_rate_limit(watchdog):
    state, _, _, _, run = watchdog
    for now in (1800000000, 1800000001, 1800021599, 1800021600):
        run(WATCHDOG_NOW_EPOCH=str(now), SWAP_USED="17.50G")
    log = (state / "watchdog.log").read_text()
    assert log.count("ALERT host swap used") == 2


def test_swap_below_95_percent_does_not_alert(watchdog):
    state, _, _, _, run = watchdog
    run(WATCHDOG_NOW_EPOCH="1800000000", SWAP_USED="16.00G")
    assert "ALERT host swap used" not in (state / "watchdog.log").read_text()


def test_missing_docker_under_env_i_is_config_error_and_never_restarts(tmp_path):
    state = tmp_path / "state"
    env = {"HOME": str(tmp_path), "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
           "WATCHDOG_STATE_DIR": str(state), "WATCHDOG_DOCKER_BIN": str(tmp_path / "missing-docker")}
    result = subprocess.run(["/usr/bin/env", "-i", *[f"{k}={v}" for k, v in env.items()], "/bin/bash", str(SCRIPT), "--check-once"], capture_output=True, text=True, timeout=5)
    assert result.returncode == 0
    assert "CONFIG ERROR docker CLI not found" in (state / "watchdog.log").read_text()


def test_dry_run_prints_plan_and_does_not_change_real_state(watchdog):
    state, _, _, _, run = watchdog
    result = run("--dry-run", ENGINE_MODE="fail", WATCHDOG_NOW_EPOCH="1800000000")
    assert result.returncode == 0
    assert list(state.iterdir()) == []
    assert "ENGINE DOWN" in result.stderr


def test_dry_run_from_state_previews_restart_without_writing_source(watchdog):
    state, _, _, _, run = watchdog
    now = 1800000360
    originals = {
        "engine_failure_count": "2\n",
        "engine_failure_since_epoch": f"{now - 360}\n",
        "last_run_epoch": f"{now - 120}\n",
        "restart_epochs": "",
    }
    for name, value in originals.items():
        (state / name).write_text(value)
    result = run("--dry-run-from-state", str(state), ENGINE_MODE="fail", WATCHDOG_NOW_EPOCH=str(now))
    assert result.returncode == 0
    assert "DRY-RUN would restart Docker Desktop" in result.stderr
    assert {name: (state / name).read_text() for name in originals} == originals
    assert not (state / "watchdog.log").exists()


def test_overlapping_run_skip_preserves_owner_lock(watchdog, tmp_path):
    state, _, _, base, _ = watchdog
    entered = tmp_path / "docker-entered"
    release = tmp_path / "docker-release"
    docker = _executable(
        tmp_path / "blocking-docker",
        'touch "$DOCKER_ENTERED"\nwhile [[ ! -e "$DOCKER_RELEASE" ]]; do /bin/sleep 0.02; done\nexit 0\n',
    )
    env = {**base, "WATCHDOG_DOCKER_BIN": str(docker), "DOCKER_ENTERED": str(entered), "DOCKER_RELEASE": str(release)}
    first = subprocess.Popen(["/bin/bash", str(SCRIPT), "--check-once"], env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and not entered.exists():
            time.sleep(0.02)
        assert entered.exists()
        owner = (state / "lock" / "owner").read_text()
        second = subprocess.run(["/bin/bash", str(SCRIPT), "--check-once"], env=env, text=True, capture_output=True, timeout=5)
        assert second.returncode == 0
        assert "SKIP watchdog already running" in (state / "watchdog.log").read_text()
        assert (state / "lock" / "owner").read_text() == owner
        assert first.poll() is None
    finally:
        release.touch()
        first.communicate(timeout=5)
    assert not (state / "lock").exists()


def test_home_unset_uses_safe_fallback(tmp_path):
    bindir = tmp_path / "bin"; bindir.mkdir()
    docker = _executable(bindir / "docker", "exit 0\n")
    state = tmp_path / "state"
    env = {"PATH": "/usr/bin:/bin:/usr/sbin:/sbin", "WATCHDOG_STATE_DIR": str(state), "WATCHDOG_DOCKER_BIN": str(docker)}
    result = subprocess.run(["/usr/bin/env", "-i", *[f"{k}={v}" for k, v in env.items()], "/bin/bash", str(SCRIPT), "--check-once"], capture_output=True, text=True, timeout=5)
    assert result.returncode == 0
    assert (state / "watchdog.log").exists()
