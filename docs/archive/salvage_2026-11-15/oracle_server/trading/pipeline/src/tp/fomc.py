"""FOMC statement times (deterministic event calendar, public schedule https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm).
Statement = last day of the meeting at 14:00 US Eastern (EST/EDT by the US DST rule) -> UTC. Fetched once by `fomc-fetch`."""
import datetime as dt
import json
import re

import requests

from .config import DATA

URL = "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"
PATH = DATA / "research" / "fomc_dates.json"
MONTHS = {m: i for i, m in enumerate(["January", "February", "March", "April", "May", "June", "July", "August", "September",
                                      "October", "November", "December"], 1)}


def us_dst(d):
    """US DST: second Sunday of March 02:00 local .. first Sunday of November 02:00 (date-level is enough for 14:00 local)."""
    mar = dt.date(d.year, 3, 1)
    start = mar + dt.timedelta(days=(6 - mar.weekday()) % 7 + 7)
    nov = dt.date(d.year, 11, 1)
    end = nov + dt.timedelta(days=(6 - nov.weekday()) % 7)
    return start <= d < end


def parse(html_text):
    out = []
    for m in re.finditer(r"(\d{4}) FOMC Meetings", html_text):
        y = int(m.group(1))
        seg = html_text[m.end(): m.end() + 30000]
        nxt = re.search(r"\d{4} FOMC Meetings", seg)
        seg = seg[: nxt.start()] if nxt else seg
        txt = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", seg))
        for mm in re.finditer(r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2})(?:-(\d{1,2}))?\*?\s+(?:Statement|Conference Call|Press Conference|Implementation)", txt):
            mon, d1, d2 = MONTHS[mm.group(1)], int(mm.group(2)), mm.group(3)
            day = int(d2) if d2 else d1
            try:
                out.append(dt.date(y, mon, day))
            except ValueError:
                pass
    return sorted(set(out))


def to_utc(d):
    return dt.datetime(d.year, d.month, d.day, 18 if us_dst(d) else 19, 0, tzinfo=dt.timezone.utc)


def fetch():
    r = requests.get(URL, headers={"User-Agent": "tp-research-collector/1.0"}, timeout=30)
    r.raise_for_status()
    dates = [d for d in parse(r.text) if 2022 <= d.year <= 2027]
    PATH.parent.mkdir(parents=True, exist_ok=True)
    PATH.write_text(json.dumps({"source": URL, "fetched": dt.datetime.now(dt.timezone.utc).isoformat(), "statement_dates": [d.isoformat() for d in dates]}))
    return dates


def statement_times():
    d = json.loads(PATH.read_text())["statement_dates"]
    return [to_utc(dt.date.fromisoformat(x)) for x in d]
