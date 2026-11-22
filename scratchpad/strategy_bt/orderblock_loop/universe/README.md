# R2 Role C equity universe rules

Both files are frozen symbol lists for descriptive TRAIN exploration only. The source panels are read with an end-date predicate at 2026-05-31. No 2026-06-01 or later OHLC rows are used.

- `US.csv`: 487 normalized symbols from the earliest S&P 500 historical-membership snapshot, 1996-01-02. A trailing `-YYYYMM` removal marker in the source component string is stripped before matching Yahoo's price-panel ticker. No symbol is added after the snapshot.
- `KR.csv`: 558 codes with an observed stock-price row on 2007-06-05, the earliest date in the current-stock panel. The code set is the union of current and delisted price panels on that date and is then held fixed.
- Both lists are **proxy fixed cohorts**, not certified complete PIT universes. The US Yahoo panel is survivor-heavy and does not provide prices for every removed S&P member. The KR snapshot is limited to observed rows and misses KRX members without a price row that day; the catalog lists 4,229 delisted names, of which 1,190 had any returned price history and 3,039 (71.86%) had none.
- Therefore all TRAIN rows must carry `PRESENT/UNKNOWN` survivorship-bias text. This data gap bars candidate freezing and TEST submission under the preregistered C3/C4 addendum.
- The CSV `daily_path` repeats the source panel path; `search_equities.py` filters one symbol per read. Weekly bars are aggregated from that symbol's daily TRAIN rows. A partial boundary week with fewer than four daily rows is omitted.
