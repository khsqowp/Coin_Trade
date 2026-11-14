"""Fetch daily history for every ticker that was an S&P 500 member at any time since 1999 (fja05680/sp500 point-in-time list).
Read-only public data via tp.usdata (cached, rate-limited). Writes a coverage log; no strategy computation here."""
import json
import sys
import time

import pandas as pd

from tp import usdata

PIT = usdata.US_DIR / "pit" / "sp500_ticker_start_end.csv"
LOG = usdata.US_DIR / "pit" / "fetch_log.json"


def yahoo_symbol(t):
    return t.replace(".", "-")


def main():
    se = pd.read_csv(PIT)
    se["end_date"] = se["end_date"].fillna("2099-12-31")
    se = se[se["end_date"] >= "1999-01-01"]
    tickers = sorted(set(se["ticker"]))
    extra = ["RSP", "IJH", "IWB", "SPY", "MDY", "QQQ", "^IRX"]
    syms = extra + [yahoo_symbol(t) for t in tickers]
    log = {"started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "n": len(syms), "ok": [], "err": {}}
    for i, s in enumerate(syms):
        try:
            usdata.fetch(s, max_age_h=24 * 7)
            log["ok"].append(s)
        except Exception as e:  # noqa: BLE001
            log["err"][s] = str(e)[:200]
        if i % 25 == 0:
            LOG.write_text(json.dumps(log))
            print(i, len(syms), len(log["ok"]), len(log["err"]), flush=True)
    log["finished"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    LOG.write_text(json.dumps(log, indent=0))
    print("done", len(log["ok"]), len(log["err"]))


if __name__ == "__main__":
    sys.exit(main())
