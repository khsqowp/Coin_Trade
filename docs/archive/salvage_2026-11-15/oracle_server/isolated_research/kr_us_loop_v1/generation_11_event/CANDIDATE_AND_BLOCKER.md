# Generation 11 event candidate audit — ex-dividend post-event reversal

Date: 2026-11-06 (Asia/Seoul)  
Status: candidate identified; **no return/performance data was calculated**. This is a data/source feasibility review, not a registered strategy test.

## Candidate not duplicated by Generations 01–10

**Ex-dividend post-event response / reversal.** Test whether dividend-paying S&P 500 constituents exhibit a systematic short-horizon total-return rebound after the ex-dividend date, after the mechanical distribution adjustment is separated from the stock's market move. This is an event/microstructure hypothesis, not a moving-average, price-momentum, or month-start exposure rule. Gen04 discussed dividend initiation/increase announcements, not post-ex-date price response; Gen01 gap reversal and Gen03 overnight/daytime trend decomposition do not condition on a corporate-action event.

The idea is mechanically distinct, but that does not imply an exploitable edge. A pre-registered version would need to define ex-date knowledge time, event eligibility, adjusted-vs-raw price treatment, execution, holding interval, overlap, weighting, costs, and benchmark before reading any performance. The local event feed only stores dividend dates/amounts; it does not document announcement timestamps, event-type classifications, source/vendor, revision history, or whether historical values are split-adjusted. Therefore this task did not choose an arbitrary yield cutoff or holding period and did not run a backtest.

## Read-only local data audit

Inputs read only:

- `../data_mirror/us_daily/*.events.json`
- `../data_mirror/us_daily/*.parquet`
- `../data_mirror/us_daily/pit/sp500_ticker_start_end.csv`

Observed counts:

| Check | Result |
|---|---:|
| Unique historical PIT tickers in membership file | 1,209 |
| Local US daily parquet files | 737 |
| Local event JSON files | 737 |
| Event files with at least one dividend row | 597 |
| Event files with empty dividend list | 140 |
| PIT tickers with a local price file | 715 |
| PIT tickers with an event file | 715 |
| PIT tickers with both a local price file and event file | 715 |
| Dividend event rows falling within a recorded PIT membership interval for those covered tickers | 33,492 |
| Those rows whose ex-date appears in the matching daily price index with adjacent sessions available | 33,483 |
| Active-member event rows without an exact price-index date match | 9 |

The nine event-date mismatches and each symbol’s event-file provenance must be examined before any test. The 140 empty dividend lists cannot safely be interpreted as verified “no dividend” histories: the data has no completeness flag. More importantly, 494 of 1,209 PIT tickers have no local price or event file; a universe-wide event portfolio would silently omit 40.9% of the recorded PIT tickers. The surviving/covered 715-name subset is not evidence of complete event coverage and can carry survivorship and symbol-history bias. A test restricted to it could be exploratory only, not a valid edge confirmation.

## Concrete blocker and next data requirements

Do not run a universe-wide event strategy on the current mirror. Required before a defensible full-universe test:

1. Daily total-return prices and raw OHLC for active **and delisted** securities, keyed by permanent security identifiers rather than ticker alone, with splits and cash distributions reconciled.
2. A PIT corporate-actions feed with ex-date, announcement/publication timestamp, action type (regular/special/stock dividend), amount and currency, split-adjustment basis, cancellations/corrections, and source provenance.
3. A coverage audit against every active PIT security-date. Missing event history must be distinguishable from an explicit no-dividend record.
4. A prospectively untouched evaluation interval and reconciled historical trial count before any confirmatory claim. Current history was already inspected by prior generations.

With a complete vendor feed, the next allowed work is one event study/portfolio rule chosen and hashed before looking at returns. Until then, this is a valid new research lead plus a data blocker—not a finding that dividend-event strategies lack an edge.

## Scope confirmation

- No price returns, strategy metrics, or candidate performance were inspected or computed here.
- No data files were edited; only this report was added under `generation_11_event/`.
- No Oracle access, live orders, commit, or push occurred.
