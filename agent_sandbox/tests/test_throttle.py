import pytest
import requests
from http_client import ThrottledHttp, BanError, ExchangeError
from state import StateStore


class Clock:
    def __init__(self):
        self.t = 1000.0
        self.sleeps = []

    def __call__(self):
        return self.t

    def sleep(self, value):
        self.sleeps.append(value)
        self.t += value


class Response:
    def __init__(self, status=200, body=None, headers=None):
        self.status_code, self.body, self.headers = (
            status,
            {} if body is None else body,
            headers or {},
        )

    def json(self):
        return self.body


class Session:
    def __init__(self, responses=None):
        self.responses = list(responses or [])
        self.calls = []

    def request(self, *args, **kw):
        self.calls.append((args, kw))
        result = self.responses.pop(0) if self.responses else Response()
        if isinstance(result, Exception):
            raise result
        return result


def test_21st_waits_shared(cfg):
    clock, session = Clock(), Session()
    a = ThrottledHttp(cfg, session=session, clock=clock, sleep=clock.sleep)
    b = ThrottledHttp(cfg, session=session, clock=clock, sleep=clock.sleep)
    for _ in range(20):
        a.get("/x")
    assert not clock.sleeps
    b.get("/x")
    assert clock.sleeps == [60]
    assert len(session.calls) == 21


@pytest.mark.parametrize(
    "status,headers,body,until",
    [
        (418, {}, {"msg": "IP banned until 1120000"}, 1120),
        (429, {"Retry-After": "120"}, {}, 1120),
    ],
)
def test_ban_persist_no_retry(cfg, status, headers, body, until):
    clock, session = Clock(), Session([Response(status, body, headers)])
    c = ThrottledHttp(cfg, session=session, clock=clock, sleep=clock.sleep)
    with pytest.raises(BanError) as exc:
        c.get("/x")
    assert exc.value.until == until and len(session.calls) == 1 and not clock.sleeps
    assert StateStore(cfg.state_dir).read("ban.json")["status"] == status
    other = ThrottledHttp(cfg, session=session, clock=clock, sleep=clock.sleep)
    with pytest.raises(BanError):
        other.get("/x")
    assert len(session.calls) == 1
    clock.t = until
    other.get("/x")
    assert len(session.calls) == 2


@pytest.mark.parametrize(
    "responses,ok",
    [
        ([Response(500), Response(503), Response(200)], True),
        ([Response(500)] * 3, False),
        ([requests.Timeout()] * 3, False),
        ([requests.ConnectionError()] * 3, False),
    ],
)
def test_backoff(cfg, responses, ok):
    clock, session = Clock(), Session(responses)
    c = ThrottledHttp(cfg, session=session, clock=clock, sleep=clock.sleep)
    if ok:
        assert c.get("/x") == {}
    else:
        with pytest.raises(ExchangeError):
            c.get("/x")
    assert len(session.calls) == 3 and clock.sleeps == [1, 2]
    assert all(call[1]["allow_redirects"] is False for call in session.calls)


def test_400_no_retry(cfg):
    clock, session = Clock(), Session([Response(400)])
    with pytest.raises(ExchangeError):
        ThrottledHttp(cfg, session=session, clock=clock, sleep=clock.sleep).get("/x")
    assert len(session.calls) == 1 and not clock.sleeps
