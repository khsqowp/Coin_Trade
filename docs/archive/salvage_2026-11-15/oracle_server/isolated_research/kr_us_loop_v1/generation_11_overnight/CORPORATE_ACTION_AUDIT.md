# Gen11 corporate-action consistency audit

- Input snapshot: `SPY.parquet` plus `SPY.events.json`; both are from the same unofficial Yahoo chart v8 source.
- Dividends: 136 event rows; all event dates are present in the normalized observed SPY date index.
- Splits: zero event rows.
- Arithmetic check: for every listed cash-dividend date, compare observed `factor[ex-date] / factor[prior session]`, where `factor = adjclose / close`, with `prior raw close / (prior raw close - event amount)`. All 136 observations were finite and comparable. Absolute relative-error median: `1.566649846518331e-7`; p95: `5.945169795351646e-7`; maximum: `9.716198503539886e-7`.
- Result: internal adjustment arithmetic is consistent with the vendor's listed dividend events to the displayed precision. The event file and adjusted-close series share one vendor, so this does not establish that the event list is complete, that vendor history has no corrections, or that actual auction fills/slippage equal the model.
- Timing: the portfolio never uses a same-close price signal. MOC is fixed by schedule and submitted before the auction cutoff; liquidation is a scheduled next-session MOO order. Actual order cutoff times and fills are unavailable in the daily-bar snapshot.
- This is a post-run audit of source fields only. It did not change the candidate, evaluate parameter variants, or rerun performance.
