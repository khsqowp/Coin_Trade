import json

import pytest

from tp import notify

TOKEN = "123456789:AAH-fake_token_value_only_for_tests_1234567"
CHAT = "55501234"


class FakeResp:
    def __init__(self, code=200, body=None):
        self.status_code, self._b = code, body or {}

    def json(self):
        return self._b


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setenv(notify.TOKEN_ENV, TOKEN)
    monkeypatch.setenv(notify.CHAT_ENV, CHAT)
    monkeypatch.setenv("SOME_API_KEY", "supersecretvalue-9999")


def test_disabled_without_config(monkeypatch):
    monkeypatch.delenv(notify.TOKEN_ENV, raising=False)
    monkeypatch.delenv(notify.CHAT_ENV, raising=False)
    calls = []
    r = notify.send("hello", _post=lambda *a, **k: calls.append(1))
    assert r["sent"] is False and "disabled" in r["reason"] and not calls


def test_disabled_when_chat_id_missing(monkeypatch):
    monkeypatch.setenv(notify.TOKEN_ENV, TOKEN)
    monkeypatch.delenv(notify.CHAT_ENV, raising=False)
    assert notify.config()["enabled"] is False
    assert notify.send("x")["sent"] is False


def test_only_sendmessage_endpoint_and_plain_text(env):
    seen = {}

    def post(url, json=None, timeout=None):
        seen.update(url=url, json=json, timeout=timeout)
        return FakeResp(200)
    r = notify.send("hi", _post=post)
    assert r == {"sent": True, "reason": "ok"}
    assert seen["url"].endswith("/sendMessage") and "getUpdates" not in seen["url"]
    assert "parse_mode" not in seen["json"] and seen["json"]["disable_web_page_preview"] is True
    assert seen["timeout"] <= 15


def test_scrub_removes_env_values_and_token_shapes(env):
    raw = ("token=%s chat=%s key=supersecretvalue-9999 sk-abcdefghijklmnop1234 Bearer abcdefghijklmnopqrstu "
           "AIzaSyA1234567890123456789012345 url https://api.telegram.org/bot%s/sendMessage "
           "hex %s") % (TOKEN, CHAT, TOKEN, "a" * 64)
    out = notify.scrub_message(raw)
    for bad in (TOKEN, CHAT, "supersecretvalue-9999", "sk-abcdefghijklmnop1234", "AIzaSy", "a" * 40, "AAH-fake_token"):
        assert bad not in out
    assert "api.telegram.org" in out


def test_key_colon_value_format_is_scrubbed():
    out = notify.scrub_message("ANTHROPIC_API_KEY: sk-live-abcdef012345\nsecret = hunter2hunter2")
    assert "abcdef012345" not in out and "hunter2hunter2" not in out


def test_exception_text_never_leaks_token_url(env):
    def post(url, **k):
        raise RuntimeError("HTTPSConnectionPool: Max retries exceeded with url: /bot%s/sendMessage" % TOKEN)
    notify_sleep = notify.time.sleep
    notify.time.sleep = lambda s: None
    try:
        r = notify.send("hi", _post=post)
    finally:
        notify.time.sleep = notify_sleep
    assert r["sent"] is False
    blob = json.dumps(r)
    assert TOKEN not in blob and "AAH-fake" not in blob and CHAT not in blob


def test_http_error_reports_description_only(env):
    notify_sleep = notify.time.sleep
    notify.time.sleep = lambda s: None
    try:
        r = notify.send("hi", _post=lambda url, **k: FakeResp(400, {"description": "Bad Request: chat not found"}))
    finally:
        notify.time.sleep = notify_sleep
    assert r["sent"] is False and "chat not found" in r["reason"] and TOKEN not in r["reason"]


def test_retry_is_bounded(env):
    n = []
    notify_sleep = notify.time.sleep
    notify.time.sleep = lambda s: None
    try:
        notify.send("hi", _post=lambda url, **k: (n.append(1), FakeResp(500))[1])
    finally:
        notify.time.sleep = notify_sleep
    assert len(n) == notify.RETRIES + 1


def test_dry_does_not_post_and_message_is_truncated(env):
    r = notify.send("x" * 10000, dry=True, _post=lambda *a, **k: pytest.fail("posted"))
    assert r["sent"] is False and len(r["preview"]) <= notify.MAX_LEN


def test_run_summary_contents_and_no_secrets(env):
    hyp = {"name": "BTC SMA ATR token=%s" % TOKEN, "symbol": "BTC/USDT", "rules": [{"name": "sma_entry"}, {"name": "atr_trailing_exit"}]}
    st = lambda **k: dict({"total_return": 0.5, "sharpe": 1.0, "mdd": 0.3, "trades": 20}, **k)
    bt = {"full": st(), "out_of_sample": st(trades=8), "buy_and_hold": {"total_return": 2.0, "mdd": 0.7}}
    audit = {"verdict": "FAIL", "findings": [{"severity": "high"}]}
    abl = {"status": "ok", "rules": [1, 2], "effective_rules": ["sma_entry"], "dead_rules": ["atr_trailing_exit"],
           "weak_rules": [], "undeclared_hypothesis_rules": []}
    gate = {"decision": "BLOCK", "reasons": ["DEAD_RULE: atr_trailing_exit"], "warnings": []}
    msg = notify.format_run_summary("run-x", "crypto", hyp, bt, audit, abl, gate, 0.0312,
                                    {"task_spent": 0.2, "allowance": 1.5}, None)
    out = notify.scrub_message(msg)
    for must in ("run-x", "BTC/USDT", "FAIL", "DEAD_RULE", "$0.0312", "BLOCK", "atr_trailing_exit"):
        assert must in out
    assert TOKEN not in out


def test_candidate_and_budget_messages():
    cand = {"id": "BTCUSDT_H1_abcd1234", "strategy_file": "f.py", "swap_command": "cd x && docker compose up", "rollback_command": "cd x"}
    m = notify.format_candidate(cand)
    assert "NOT deployed" in m and "owner approval" in m and "docker compose" in m
    assert "80%" in notify.format_budget_warning(1.2, 1.5) or "BUDGET" in notify.format_budget_warning(1.2, 1.5)
