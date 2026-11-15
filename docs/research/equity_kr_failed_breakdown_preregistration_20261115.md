# KR daily failed-breakdown reversal: fixed exploratory protocol

Status: exploratory development-data test only. The local caches and historical period have previously been analyzed; this document does not create an untouched holdout or authorize trading.

## Frozen hypothesis and rules

Among the currently cached Korean common stocks, a fresh 20-session low that is rejected by the close may predict a short-term rebound. At the signal close `t`, define `L20[t] = min(Low[t-20:t])`. Emit a long signal only when `Low[t] < L20[t]` and `Close[t] > L20[t]`. Enter at the next market session's open. Exit at the close of the fifth holding session, counting the entry session as session one. Do not add stops, profit targets, trend filters, parameter search, or discretionary exclusions. Suppress a ticker's new signal until its existing event exits. This is an event-study screen, not an account portfolio.

## Data, universe and causality

Use only local `KR_*.csv` daily OHLCV files and the `KR_069500.csv` market proxy. Exclude the frozen ETF list in `equity_kr_failed_breakdown_probe.py`. Require every one of the 20 lookback sessions, signal session, next-session entry, and five-session holding path to exist for both stock and benchmark. Do not forward-fill or interpolate. Read only rows dated before the exclusive cutoff `2024-11-12`; parse the timestamp of the cutoff row only to stop. The signal uses completed OHLC at `t`, with entry no earlier than `t+1` open. Hash only header and pre-cutoff rows, not later file contents.

## Costs and benchmark

Stock base cost: 0.015% buy commission, 0.015% sell commission, 0.18% sell tax, and 0.10% slippage on each side. Stress doubles slippage to 0.20% per side. The matched benchmark buys 069500 at the same next-session open and exits at the same fifth-session close, with 0.015% commission and 0.10%/0.20% assumed slippage per side and no sell tax. These are scenario assumptions; actual fills and historical tax classification are not observed. Report gross and net trade returns, positive-return rate, paired return minus benchmark, counts, coverage per symbol, yearly breakdown, and six-calendar-month circular block-bootstrap intervals.

## Decision and interpretation

Report all observations even if unfavorable. A positive result is not validation because the source cohort is current/survivor-selected and the historical database has been repeatedly inspected. Block intervals are descriptive and do not correct strategy-family or symbol-selection multiplicity. A negative result rejects this fixed candidate on the development cache only; it does not show that all Korean strategies fail. Any future validation must freeze a new prospective rule before collecting its outcomes and needs point-in-time membership, delisted securities, corporate-action provenance, and executable quotes.
