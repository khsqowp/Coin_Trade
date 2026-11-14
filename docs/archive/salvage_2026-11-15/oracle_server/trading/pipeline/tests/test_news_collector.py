import datetime as dt
import time

import pytest

from tp import news

RSS = b"""<?xml version="1.0"?><rss version="2.0"><channel><title>t</title>
<item><title>Fed holds rates &lt;b&gt;steady&lt;/b&gt;</title><link>https://x.test/a</link><guid>g1</guid>
<description><![CDATA[<p>Policy <i>unchanged</i></p>]]></description><pubDate>Sat, 24 Oct 2026 12:00:00 GMT</pubDate></item>
<item><title>Second</title><link>https://x.test/b</link><guid>g2</guid><pubDate>Mon, 01 Jan 2035 00:00:00 GMT</pubDate></item>
</channel></rss>"""
ATOM = b"""<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>A</title><id>i1</id><link href="https://x.test/c"/><updated>2026-10-24T01:02:03Z</updated><summary>S</summary></entry></feed>"""


@pytest.fixture()
def con(tmp_path, monkeypatch):
    monkeypatch.setattr(news, "NEWS_DIR", tmp_path)
    monkeypatch.setattr(news, "DB", tmp_path / "n.sqlite")
    return news.db()


def test_parse_rss_and_atom():
    r = news.parse_feed(RSS)
    assert [x["guid"] for x in r] == ["g1", "g2"] and r[0]["published"].year == 2026
    a = news.parse_feed(ATOM)
    assert a[0]["link"] == "https://x.test/c" and a[0]["published"].hour == 1


def test_entity_declarations_rejected():
    evil = b'<?xml version="1.0"?><!DOCTYPE r [<!ENTITY a "aaaa">]><rss><channel><item><title>&a;</title></item></channel></rss>'
    with pytest.raises(ValueError):
        news.parse_feed(evil)


def test_clean_text_strips_markup_and_controls():
    t = news.clean_text("<script>x</script>Hello&nbsp;<b>w</b>\x00‮orld", 100)
    assert "<" not in t and "\x00" not in t and "‮" not in t


def test_store_dedup_clamp_and_revision(con):
    now = dt.datetime(2026, 10, 25, tzinfo=dt.timezone.utc)
    ents = news.parse_feed(RSS)
    assert news.store_items(con, "fed", "global", "u", ents, now) == 2
    assert news.store_items(con, "fed", "global", "u", ents, now + dt.timedelta(minutes=5)) == 0     # dedup
    row = con.execute("SELECT published_at, extra FROM items WHERE title='Second'").fetchone()
    assert row[0] == "2026-10-25T00:00:00Z" and "published_clamped" in row[1]                      # future date clamped
    edited = [dict(ents[0], raw=ents[0]["raw"] + "edited")]
    news.store_items(con, "fed", "global", "u", edited, now + dt.timedelta(hours=1))
    assert con.execute("SELECT COUNT(*) FROM item_revisions").fetchone()[0] == 1
    assert con.execute("SELECT COUNT(*) FROM items").fetchone()[0] == 2                              # first-seen row immutable


def test_asof_excludes_later_data(con):
    t0 = dt.datetime(2026, 10, 25, 0, 0, tzinfo=dt.timezone.utc)
    news.store_items(con, "bbc", "global", "u", [dict(guid="a", link="l", title="early", summary="", published=t0, raw="a")], t0)
    news.store_items(con, "bbc", "global", "u", [dict(guid="b", link="l", title="late", summary="", published=t0 + dt.timedelta(hours=2), raw="b")],
                     t0 + dt.timedelta(hours=2))
    got = [i["title"] for i in news.items_asof(con, t0 + dt.timedelta(hours=1))]
    assert got == ["early"]
    # item published earlier but only FETCHED later must also be excluded (knowledge time = fetched_at)
    news.store_items(con, "bbc", "global", "u", [dict(guid="c", link="l", title="backfilled", summary="", published=t0, raw="c")],
                     t0 + dt.timedelta(hours=3))
    assert "backfilled" not in [i["title"] for i in news.items_asof(con, t0 + dt.timedelta(hours=1))]
    news.store_feature(con, "fear_greed", "2026-10-25T05:00:00Z", 10, t0 + dt.timedelta(hours=5), "u", "raw")
    assert news.features_asof(con, t0 + dt.timedelta(hours=1)) == []


def test_backoff_grows_and_caps():
    d = [news.backoff_delay(f, 600, rnd=lambda: 0.5) for f in range(0, 12)]
    assert d == sorted(d) and max(d) <= 3600 * 1.2 + 1e-9
    assert news.backoff_delay(1, 60, retry_after=1800, rnd=lambda: 0.5) >= 1800


def test_us_partial_bar_dropped():
    # market close 21:30 UTC rule: a bar for the current UTC date is not final before 21:30
    day = dt.date(2026, 10, 23)
    assert not news._et_close_passed(day, dt.datetime(2026, 10, 23, 18, 0, tzinfo=dt.timezone.utc))
    assert news._et_close_passed(day, dt.datetime(2026, 10, 23, 22, 0, tzinfo=dt.timezone.utc))


def test_rss_fallback_url_used(con, monkeypatch):
    calls = []

    def fake_get(url, **kw):
        calls.append(url)
        if "primary" in url:
            raise news.FetchError("HTTP 503", 503)
        return 200, RSS
    monkeypatch.setattr(news, "http_get", fake_get)
    n = news.job_rss(con, {"id": "coindesk", "market": "crypto", "urls": ["https://primary.test", "https://fallback.test"]})
    assert n == 2 and calls == ["https://primary.test", "https://fallback.test"]


# ---------------------------------------------------------------- GDELT rate-limit hardening
class _Resp:
    def __init__(self, code, body=b"{}", headers=None):
        self.status_code, self.headers = code, headers or {}
        import io
        b = io.BytesIO(body)
        self.raw = type("R", (), {"read": staticmethod(lambda n, decode_content=True: b.read(n))})()


def _fake_requests(monkeypatch, codes, calls):
    def fake(url, params=None, **kw):
        calls.append((url, dict(params or {})))
        c = codes.pop(0) if codes else 200
        if isinstance(c, tuple):
            return _Resp(c[0], headers=c[1])
        return _Resp(c)
    monkeypatch.setattr(news.requests, "get", fake)


def test_timeline_once_per_day(con, monkeypatch):
    modes = []

    def fake_get(url, params=None, **kw):
        modes.append(params["mode"])
        return 200, b'{"articles": []}' if params["mode"] == "artlist" else b'{"timeline": [{"data": [{"date": "20261025T000000Z", "value": 1.5}]}]}'
    monkeypatch.setattr(news, "http_get", fake_get)
    news.job_gdelt(con, "monetary")
    news.job_gdelt(con, "monetary")
    news.job_gdelt(con, "korea")
    assert modes == ["artlist", "timelinetone", "artlist", "artlist", "timelinetone"]
    con.execute("UPDATE fetch_log SET at='2026-01-01T00:00:00Z' WHERE job='gdelt_tone:monetary'")
    news.job_gdelt(con, "monetary")
    assert modes[-2:] == ["artlist", "timelinetone"]


def test_timeline_failure_keeps_artlist(con, monkeypatch):
    def fake_get(url, params=None, **kw):
        if params["mode"] == "timelinetone":
            raise news.FetchError("HTTP 429", 429)
        return 200, b'{"articles": [{"url": "https://x.test/1", "title": "t", "seendate": "20261025T000000Z"}]}'
    monkeypatch.setattr(news, "http_get", fake_get)
    assert news.job_gdelt(con, "monetary") == 1
    assert news.tone_due(con, "monetary")        # failed attempt does not count as done


def test_shared_cooldown_blocks_all_gdelt_jobs(con, monkeypatch):
    calls = []
    _fake_requests(monkeypatch, [429], calls)
    with pytest.raises(news.FetchError) as ei:
        news.job_gdelt(con, "monetary", sleep=lambda s: None)
    assert ei.value.http == 429 and len(calls) == 1
    assert news.cooldown_remaining() > 0
    for q in ("geopolitics", "crypto_policy", "korea"):      # other jobs must not touch the network
        with pytest.raises(news.CooldownActive):
            news.job_gdelt(con, q, sleep=lambda s: None)
    assert len(calls) == 1
    # non-gdelt hosts are unaffected
    _fake_requests(monkeypatch, [200], calls)
    assert news.http_get("https://other.test/x", sleep=lambda s: None)[0] == 200


def test_cooldown_expires_and_success_resets(con, monkeypatch):
    news.note_429(now=1000.0)
    assert news.cooldown_remaining(now=1000.0 + 10) > 0
    assert news.cooldown_remaining(now=1000.0 + news.COOLDOWN_BASE_S + 1) == 0
    calls = []
    _fake_requests(monkeypatch, [200], calls)
    monkeypatch.setattr(news.time, "time", lambda: 1e12)
    news.http_get(news.GDELT_BASE, sleep=lambda s: None)
    assert news.cooldown_state()["consec"] == 0


def test_cooldown_backoff_grows_and_caps(con):
    d = [news.cooldown_delay(n) for n in range(1, 20)]
    assert d == sorted(d) and d[0] == news.COOLDOWN_BASE_S
    assert max(d) == news.COOLDOWN_CAP_S == 6 * 3600
    assert news.cooldown_delay(1000) == news.COOLDOWN_CAP_S
    st = None
    for i in range(10):
        st = news.note_429(now=0.0)
    assert st["consec"] == 10 and st["until"] == news.COOLDOWN_CAP_S


def test_retry_after_honoured_and_bounded(con, monkeypatch):
    assert news.cooldown_delay(1, retry_after=3 * 3600) == 3 * 3600
    assert news.cooldown_delay(5, retry_after=60) == 4 * 3600          # never shorter than our own backoff
    assert news.cooldown_delay(1, retry_after=10 ** 9) == news.RETRY_AFTER_MAX_S
    calls = []
    _fake_requests(monkeypatch, [(429, {"Retry-After": "7200"})], calls)
    with pytest.raises(news.FetchError) as ei:
        news.http_get(news.GDELT_BASE, sleep=lambda s: None)
    assert ei.value.retry_after == 7200
    assert news.cooldown_remaining() > 7000


def test_gdelt_schedule_is_staggered_and_slow():
    jobs = news.build_jobs()
    g = {k: v for k, v in jobs.items() if k.startswith("gdelt:")}
    assert len(g) == 4 and all(v["every"] >= 7200 for v in g.values())
    offs = sorted(v["offset"] for v in g.values())
    assert min(b - a for a, b in zip(offs, offs[1:])) >= 600
    assert news.HOST_MIN_INTERVAL[news.GDELT_HOST] >= 15


def test_run_forever_cooldown_defers_without_failure(con, monkeypatch):
    news.note_429(now=time.time())
    def job(c):
        raise news.CooldownActive("cd", 429, 3600)
    t = [0.0]
    jobs = {"gdelt:x": dict(every=7200, fn=job)}
    seen = {}
    def stop():
        return t[0] > 20
    def sl(s):
        t[0] += 10
    monkeypatch.setattr(news, "write_status", lambda o: seen.update(o))
    news.run_forever(stop=stop, clock=lambda: t[0], sleep=sl, jobs=jobs)
    st = seen["jobs"]["gdelt:x"]
    assert st["fails"] == 0 and st["due"] > 3600


def test_watchdog_aggregates_gdelt(con, monkeypatch):
    from tp import watch
    now = dt.datetime(2026, 10, 26, tzinfo=dt.timezone.utc)
    jobs = {"gdelt:" + q: {"fails": 9, "last_ok": None, "last_err": "FetchError: HTTP 429"} for q in news.GDELT_QUERIES}
    assert watch.gdelt_issue(jobs, now) is None or "gdelt" in watch.gdelt_issue(jobs, now)
    news.note_429(now=now.timestamp())
    m = watch.gdelt_issue(jobs, now)
    assert m.startswith("KNOWN DEGRADED gdelt") and "4/4" in m
    # one aggregated issue key, no per-job keys
    monkeypatch.setattr(news, "STATUS", news.NEWS_DIR / "status.json")
    monkeypatch.setattr(watch.shutil, "disk_usage", lambda p: type("U", (), {"free": 90, "total": 100})())
    news.write_status({"updated": watch.dt.datetime.now(dt.timezone.utc).isoformat(), "jobs": jobs})
    iss = watch.check_all(dt.datetime.now(dt.timezone.utc))
    assert "gdelt_degraded" in iss and not [k for k in iss if k.startswith("news_job_gdelt")]
