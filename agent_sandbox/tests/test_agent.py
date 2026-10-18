from pathlib import Path
from types import SimpleNamespace
import subprocess
from agent import run_agent, scrub_environment, render_prompt


def test_scrub():
    env = {
        "BINANCE_FUTURE_TESTNET_API_KEY": "private",
        "MY_SECRET": "private",
        "ACCESS_TOKEN": "private",
        "OPENAI_API_KEY": "auth",
        "CODEX_TOKEN": "auth2",
        "PATH": "/bin",
        "HOME": "/home",
    }
    assert scrub_environment(env) == {
        "OPENAI_API_KEY": "auth",
        "CODEX_TOKEN": "auth2",
        "PATH": "/bin",
        "HOME": "/home",
    }


def test_runner_args(cfg, monkeypatch):
    monkeypatch.setenv("BINANCE_FUTURE_TESTNET_SECRET_KEY", "not-visible")

    def runner(cmd, **kw):
        assert "--ignore-user-config" not in cmd
        assert cmd[cmd.index("--sandbox") + 1] == "read-only"
        assert cmd[-1] == "-" and kw["input"] == "prompt"
        assert not list(Path(cmd[cmd.index("-C") + 1]).iterdir())
        assert "BINANCE_FUTURE_TESTNET_SECRET_KEY" not in kw["env"]
        assert kw["timeout"] == 600 and 'web_search="live"' in cmd
        Path(cmd[cmd.index("-o") + 1]).write_text('{"actions":[],"notes":""}')
        return SimpleNamespace(returncode=0)

    result = run_agent("prompt", cfg, runner)
    assert result.ok and result.text.startswith("{")


def test_runner_failures(cfg):
    assert not run_agent("", cfg, lambda *a, **kw: SimpleNamespace(returncode=1)).ok

    def timeout(*a, **kw):
        raise subprocess.TimeoutExpired("codex", 1)

    assert not run_agent("", cfg, timeout).ok
    assert not run_agent("", cfg, lambda *a, **kw: SimpleNamespace(returncode=0)).ok
