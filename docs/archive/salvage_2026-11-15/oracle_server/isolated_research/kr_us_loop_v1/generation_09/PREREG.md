# Generation 09 — US first-three-session calendar exposure

Registered: 2026-11-06 (Asia/Seoul), before the market-data run. One US index-ETF hypothesis only. This is price/calendar-only and exploratory; it does not qualify as confirmation because this local history has already been inspected in earlier research.

## Rationale and overlap

The hypothesis tests the published turn-of-month/early-month return pattern using only the first three exchange sessions of each calendar month. Prior literature reports positive returns around month boundaries, while a 2025 paper reports that the US effect disappeared after 2001. This conflicting evidence makes the candidate worth a bounded replication check, not a presumed edge. It is a seasonal exposure rule, not a trend signal; it is distinct from the tested cross-sectional same-calendar-month feature, but belongs to the broader calendar-seasonality family and is not an independent family-wise discovery.

Primary references: McConnell & Xu (2008), https://doi.org/10.2469/faj.v64.n2.11 ; Han, Lee & Choi (2025), https://doi.org/10.1016/j.frl.2024.106461 . The reported findings motivate the hypothesis only and do not validate this implementation.

## Frozen rule

1. Instrument: SPY only; no constituent ranking, leverage, shorting, or alternative assets. Use the existing local SPY daily parquet, with adjusted open `open * adjclose / close` to include distributions/splits consistently with adjusted-close returns. Require finite positive OHLC and internally consistent high/low bounds on every used session; fail closed otherwise.
2. Calendar: use the SPY observed session index. At each session open, target exposure is 100% SPY for the first three sessions of each calendar month, measured as open-to-next-open holding intervals. All other sessions target 0% cash. Exclude the first and final calendar-month fragments in the file so an incomplete sample boundary is not treated as a full month. No signal uses future price values; session ordering is used only to count the first three observed sessions of the current month. The local vendor feed's session completeness is not independently validated against an authoritative exchange calendar; a missing session could change the count. This remains an explicit data limitation and precludes confirmatory interpretation.
3. Execution: position changes occur at session open; PnL for each holding interval is adjusted-open-to-adjusted-open. Charge 10 bp on each 100% entry/exit turnover. The final open position is liquidated at the sample boundary and charged the same sell fee. No intraday fill assumption, margin, or interest on cash.
4. Benchmark: SPY buy-and-hold on the identical dates and adjusted-open series, with matching 10 bp initial and terminal costs. Report net metrics; gross metrics may be added only if computed by the same simulator. Strategy acceptance uses net results.
5. Report full sample and fixed descriptive partitions 2001–2016 and 2017–last available session. The later partition is already inspected and is not OOS. Do not call this a valid strategy even if any displayed partition looks favorable.

## Stop / interpretation

- Exactly one fixed test; no window, session-count, or market selection variants after observing results.
- Invalid OHLC, date/index inconsistency, non-finite returns, or missing SPY price data fails the run and remains in the attempt ledger.
- No parameter search, no claim of global DSR/PSR or family-wise significance: complete historical trial count is unresolved and calendar-seasonality is a correlated family.
- A result can only reject/support this fixed exploratory rule on this snapshot. It cannot establish an investable edge or satisfy the objective's untouched-OOS, point-in-time/corporate-action, and multiple-testing gates.
