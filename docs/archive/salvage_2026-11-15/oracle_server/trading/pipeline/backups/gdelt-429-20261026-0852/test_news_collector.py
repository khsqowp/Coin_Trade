import datetime as dt

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
