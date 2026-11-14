"""Retention policy (conservative; documented in README). NEVER touched: runs/regime_log.sqlite, runs/ledger.jsonl, forward/arena
records, strategy files, news items, features, klines, KIS minute bars, Binance liquidation/OI/long-short/funding history.
Only these are pruned:
  * news.sqlite `fetch_log` rows older than 90 days (operational log, no research value)
  * hl.sqlite `positions` rows older than 30 days are THINNED to one row per (address, coin, hour) (not removed entirely)
  * docker json logs are rotated by the container runtime (5 MB x 3).
Disk guard: the watchdog only ALERTS on low disk; it never deletes."""
import datetime as dt


def prune_news(con, now=None, days=90):
    now = now or dt.datetime.now(dt.timezone.utc)
    cut = (now - dt.timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    n = con.execute("DELETE FROM fetch_log WHERE at<?", (cut,)).rowcount
    con.commit()
    return {"fetch_log_deleted": n}


def thin_hl(con, now=None, days=30):
    now = now or dt.datetime.now(dt.timezone.utc)
    cut = (now - dt.timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    cur = con.execute("""DELETE FROM positions WHERE snap_ts<? AND rowid NOT IN (
        SELECT MIN(rowid) FROM positions WHERE snap_ts<? GROUP BY addr, coin, substr(snap_ts,1,13))""", (cut, cut))
    con.commit()
    return {"hl_positions_thinned": cur.rowcount}
