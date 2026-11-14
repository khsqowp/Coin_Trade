"""Persistent, append-only event log for the watchdog (runs/watch_events.jsonl) - the place for errors that are not live status.

One JSON object per line: {"ts": UTC ISO, "kind": ..., ...fields}. Free-text fields are scrubbed (config.scrub + notify.scrub_message) and capped at
160 characters; callers never pass the message body (it is not intentionally logged); output is ASCII-escaped JSON. Size-capped rotation (MAX_BYTES x KEEP files: events, .1, .2), mode 0600, nothing is kept in memory,
and every failure is swallowed - logging must never crash the watch loop. `summary()` builds the sanitised digest exported to Hermes (never raw lines)."""
import collections
import datetime as dt
import json
import os

from .config import RUNS, scrub

PATH = RUNS / "watch_events.jsonl"
MAX_BYTES, KEEP, DESC_MAX = 5_000_000, 3, 160


def _clean(v):
    if isinstance(v, (bool, int, float)) or v is None:
        return v
    try:
        from . import notify
        return notify.scrub_message(scrub(v, DESC_MAX), limit=DESC_MAX)
    except Exception:       # noqa: BLE001
        return "?"


def _rotate(path):
    for i in range(KEEP - 1, 0, -1):
        src = path if i == 1 else path.with_name("%s.%d" % (path.name, i - 1))
        if src.exists():
            os.replace(src, path.with_name("%s.%d" % (path.name, i)))


def log(kind, /, **fields):
    """Append one event. Never raises."""
    try:
        rec = {str(k)[:30]: _clean(v) for k, v in fields.items()}
        rec.update(ts=dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), kind=str(kind)[:40])      # ts / kind can never be overridden
        data = (json.dumps(rec, ensure_ascii=True, separators=(",", ":")) + "\n").encode("utf-8")
        path = PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.stat().st_size + len(data) > MAX_BYTES:
            _rotate(path)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        try:
            os.fchmod(fd, 0o600)
            os.write(fd, data)
        finally:
            os.close(fd)
    except Exception:       # noqa: BLE001
        pass


def _read(path):
    for i in range(KEEP - 1, -1, -1):
        p = path if i == 0 else path.with_name("%s.%d" % (path.name, i))
        try:
            with open(p, encoding="utf-8", errors="replace") as f:
                for line in f:
                    try:
                        r = json.loads(line)
                    except ValueError:
                        continue
                    if isinstance(r, dict) and isinstance(r.get("ts"), str) and isinstance(r.get("kind"), str):
                        yield r
        except OSError:
            continue


def summary(now, send_stats=None, path=None, sanitize=lambda s, n=160: s):
    """Digest for Hermes: counts by kind / HTTP code for 24 h and 7 d, first/last seen per kind, last 30 events, send_stats (streamed, bounded memory)."""
    iso = lambda d: d.strftime("%Y-%m-%dT%H:%M:%SZ")      # noqa: E731
    c24, c7 = iso(now - dt.timedelta(hours=24)), iso(now - dt.timedelta(days=7))
    out = {"window_24h": {"by_kind": collections.Counter(), "by_http": collections.Counter()},
           "window_7d": {"by_kind": collections.Counter(), "by_http": collections.Counter()}}
    seen, last = {}, collections.deque(maxlen=30)
    for r in _read(path or PATH):
        ts, kind = r["ts"], r["kind"]
        s = seen.setdefault(kind, {"first": ts, "last": ts})
        s["first"], s["last"] = min(s["first"], ts), max(s["last"], ts)
        last.append(r)
        for win, cut in (("window_24h", c24), ("window_7d", c7)):
            if ts >= cut:
                out[win]["by_kind"][kind] += 1
                if r.get("http") is not None:
                    out[win]["by_http"][str(r["http"])] += 1
    san = lambda x, n=60: sanitize(str(x), n)      # noqa: E731
    val = lambda v: v if isinstance(v, (bool, int, float)) or v is None else sanitize(str(v), DESC_MAX)      # noqa: E731
    return {"counts": {w: {k: {san(a): b for a, b in v.items()} for k, v in d.items()} for w, d in out.items()},
            "first_last_seen_per_kind": {san(k): v for k, v in seen.items()},
            "last_30_events": [{san(k, 30): val(v) for k, v in r.items()} for r in last],
            "send_stats": send_stats or {}}
