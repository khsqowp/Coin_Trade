# Generation 10 preregistration — NR7 close-confirmed breakout on SPY

- Candidate: one long-only, single-position NR7 prior-range breakout, on SPY only.
- Source rule: `trading/app/new_strategy_screening.py:181-184`. At close `t`, the prior session's range `High[t-1]-Low[t-1]` must equal the minimum of the seven observed ranges `High[t-7:t]` (the seven sessions `t-7 ... t-1`; ties qualify), and `Close[t] > High[t-1]`.
- Signal is known only after close `t`; evaluate the source indicator on unadjusted OHLC (the source rule uses OHLC and this avoids dividend-adjustment artifacts changing range ranks); enter at the next observed session's open `t+1` using adjusted open for total-return-consistent PnL.
- Exit at the open ten observed sessions after entry (`entry index + 10`). No stop, re-entry during an active trade, shorting, leverage, parameter search, or parameter variants. A signal whose full scheduled exit is outside the file is counted as terminal-censored and not traded.
- Only one open position is allowed. A signal is accepted only if its next-open entry is at or after the prior scheduled exit open; otherwise it is counted as overlap-suppressed.
- Construct adjusted open for PnL by `open * adjclose / close`. This vendor adjustment method is not independently validated and will be disclosed. Raw OHLC remains the signal series; no adjusted-OHLC values are used for triggers.
- Gross position return is adjusted-open to adjusted-open for exactly ten intervals. Charge 10 bp at entry and 10 bp at exit multiplicatively at the first and final invested intervals. Cash earns zero. Benchmark is SPY buy-and-hold over the same observed intervals with 10 bp entry and exit costs.
- Fixed descriptive windows: full history, 2001-01-01 through 2016-12-31, and 2017-01-01 onward. Partition metrics are slices of the one continuous strategy and continuous buy-and-hold portfolios; no artificial window-boundary trades/fees are introduced. The later window is known to have been inspected and is not OOS. No inferential or confirmatory claim will be made from this repeated historical snapshot.
- Integrity gate: unique, ascending normalized dates; finite positive OHLC/adjusted close; raw OHLC relationships valid; adjusted O/H/L/C and adjusted open finite/positive and internally ordered; enough rows for signal and scheduled-exit rules. Fail closed rather than drop/repair rows.
- One candidate / one planned run. Ten sessions is preselected from the source harness's existing 5/10/20 exit grid; 5 and 20 are intentionally not run. This choice is a research degree of freedom, so the result is exploratory and the tested family includes NR7/breakout and horizon selection, not one independent alpha trial. It overlaps prior breakout research. Complete global trial count and untouched OOS remain unresolved; do not claim DSR/BH significance or strategy validity.
- Decision rule: report metrics and reject this fixed rule for the stated objective if it fails to beat same-window SPY buy-and-hold on net CAGR and Sharpe in any required window. If it beats those descriptive comparisons, it remains a lead only until independent data/calendar/trial-count/OOS validation.
- Research budget for this generation: one candidate, one run, no threshold/holding-period tuning. All attempts, including integrity-gate failure, are recorded.

## Freeze record

This document is frozen before reading the SPY market file. Its SHA-256 is recorded in the run manifest and attempt ledger. Any change requires a dated addendum and a new candidate identifier.
