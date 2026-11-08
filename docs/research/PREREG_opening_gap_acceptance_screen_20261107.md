# Preregistration — Daily opening-gap acceptance/rejection screen

Registered: 2026-11-07 Asia/Seoul  
Status: `CURRENT-CACHE / SURVIVOR-COHORT / exploratory only`  
Purpose: test a price mechanism not equivalent to the previously tested close-to-close “gap” filters. This is not valid S&P 500/KOSPI 100/200 point-in-time evidence and cannot count toward the two valid-strategy target.

## Frozen data universe

- US: all 54 US tickers present in the local `.kis-cache` on registration date.
- KR: all 64 KR tickers present in the local `.kis-cache` on registration date.
- Freeze membership by recording the exact ticker list and a canonical SHA-256 manifest of every input CSV before any performance run. Do not silently add/remove names after seeing results. Initial metadata audit found 118 files (54 US, 64 KR); US dates span 2,221 union sessions and KR dates span 2,166 union sessions. These counts are metadata only, not performance evidence.
- Frozen US symbols (54): `AAON, AAPL, ADBE, AMAT, AMD, AMZN, APO, BAC, BKNG, CASY, CIEN, COST, CSCO, CVNA, DELL, DIS, FICO, FIX, GE, GLW, GOLD, GOOGL, GRC, HBAN, HD, HOOD, IBKR, IBM, INTC, JNJ, JPM, KEY, KKR, KMI, KO, LRCX, MA, META, MSFT, NFLX, NTRS, NUE, NVDA, PEP, PG, QCOM, RCL, RF, SAIA, T, TSLA, UNH, V, XOM`.
- Frozen KR symbols (64): `000270, 000660, 000720, 000810, 001270, 001510, 003230, 003540, 003670, 003690, 005180, 005380, 005490, 005930, 005940, 006400, 006800, 007660, 009150, 010130, 010950, 011170, 011200, 011790, 012330, 015760, 017670, 018260, 022100, 024110, 028260, 029780, 030200, 032830, 034730, 035420, 035720, 036570, 041830, 042700, 047810, 051900, 051910, 055550, 058470, 068270, 082640, 086790, 090430, 096770, 097950, 105560, 161890, 207940, 214150, 214450, 259960, 298040, 307950, 316140, 323410, 352820, 373220, 402340`.
- Input-file manifest SHA-256: `f29dadb38ffc051144d1f12f41b220004bd27fe9b80f3de1d50dfb668f50f336`, computed from files sorted by `.kis-cache/<filename>`, with each UTF-8 line `relative_path<TAB>sha256(file_bytes)\n`. Recompute before any test; any mismatch invalidates this frozen run.
- The cache is a current, selected KIS data subset; it is not a complete historical S&P 500/KODEX 100/200 membership universe. It may contain survivorship/selection bias. KIS adjusted OHLC behavior and historical revision policy are not independently verified.
- Only cached daily OHLCV is used. Do not download/replace/fill data. Do not infer historical constituents, sectors, earnings, dividends, or corporate actions.

## Periods and baseline

- IS: 2018-01-01 through 2022-12-30.
- Calendar: the union of all observed dates within each market. A symbol with no bar on a union date has no signal or fill on that date; an existing position is marked at its last valid close. Do not mistake the union for an official exchange calendar.
- OOS: 2023-01-01 through the last union date in each market.
- IS and OOS are independent cash accounts, each initialized to NAV 1.0. No pre-segment holdings, cash, or pending orders cross the boundary. A signal is usable only if its close date is inside that segment; fill is the next observed market date's open.
- Baseline: the same segment's fixed-cohort, equal-gross buy-and-hold account. For N names, set each gross target to `G = segment_start_NAV / (N * (1 + buy_fee_rate))`; buy names with a valid first-date open then, and reserve each later-starting name's `G*(1+buy_fee_rate)` cash slot until its first valid open. Shares remain fixed and are never rebalanced. At the final union-date close, liquidate each holding at its most recent valid close (forward-marked if the ticker lacks a final-date bar) and charge the applicable sell cost, matching the candidate account's terminal liquidation convention. This is a current-cache cohort baseline, not an index.
- Two hypotheses are separate portfolios. They do not share capital, signals, positions, or K slots.
- Each signal hypothesis × market × cost × segment is an independent cash account. K is per hypothesis account (US 11, KR 13), not shared between the two hypotheses.
- Report all IS/OOS results, year-by-year OOS returns, turnover, total fees/tax/slippage, trades, exposure/cash, event counts, stale/missing bars, and benchmark differences. No p-value/DSR/edge claim from this screen.

## Shared signal and execution definition

For each symbol and date t, define the opening gap `G_t = Open_t / Close_(t-1) - 1`, where `t-1` is the immediately preceding date in that market's frozen union calendar. If the symbol lacks a valid close on exactly `t-1`, skip the signal; do not bridge a missing date with a multi-session return. Define `sigma_t` as the population standard deviation (`ddof=0`) of close-to-close simple returns over the 20 union-calendar intervals immediately before t. Require valid closes on all 21 dates needed for those returns, so all returns are one-union-session returns; t's return is not included. Require `sigma_t > 0` and positive finite OHLC values. Use no interpolation.

The event is confirmed only at close t. Entry executes at the next union date's open only if that symbol has a valid open on that exact date; otherwise the signal expires unfilled. Each position exits at the open exactly five union market sessions after its entry open; if that symbol has no valid open on the scheduled exit date, keep it open and retry the exit at that symbol's next valid open. No stop, target, trailing exit, or discretionary exit. At each open, mark existing positions from their prior close to the current open when available, execute due exits first, then use remaining cash for new entries. Entry signals are ranked separately for each hypothesis. For each accepted entry, target gross notional is `min(NAV_before_entries/K, available_cash/(1+buy_fee_rate))`; skip further entries if cash cannot afford the next target. This makes the cash constraint deterministic and prevents negative cash even when held positions drift. At the final union-date close of each scored segment, any still-open position is liquidated at its most recent valid close (forward-marked if that ticker has no bar on the final date) and charged the applicable sell cost; this is a terminal valuation convention, not proof that a real market exit was available at that price. Shares change only on fills; daily NAV is cash plus fixed shares marked to cached closes. No shorting, leverage, cash interest, or overlapping holdings in the same symbol.

At a given entry open, rank new eligible signals by `abs(G_t / sigma_t)` descending, then ticker ascending. Allow at most `K=ceil(0.20*N)` open slots per hypothesis account. A signal is skipped if its symbol is already held or all slots are occupied. Unused slots remain cash. Deduct costs at each fill; never allow negative cash. Per union date, count turnover as `(gross buys + gross sells) / NAV immediately before the first fill on that date`.

## Two frozen hypotheses

1. `GAP_UP_ACCEPTANCE_2SIGMA`: if `G_t >= 2*sigma_t` and `Close_t > Open_t`, buy at next observed open and hold the fixed five-session interval.
2. `GAP_DOWN_REJECTION_2SIGMA`: if `G_t <= -2*sigma_t` and `Close_t > Open_t`, buy at next observed open and hold the fixed five-session interval.

No parameter search, threshold tuning, or post-result rule changes. Any change requires a new dated addendum and is not pooled with these results.

## Costs

- US base: 0.08% one-way; stress: 0.36% one-way.
- KR base: buy commission 0.015% + slippage 0.05%; sell commission 0.015% + fixed exploratory sell-tax assumption 0.18% + slippage 0.05%.
- KR stress: double slippage only; keep commission and fixed sell-tax assumption unchanged.
- KR tax is an exploratory fixed friction assumption, not historical statutory tax accounting. Slippage assumptions are not execution-validated.

## Metric and pass definitions

- Segment-start NAV 1.0 is the pre-fill state before the first union date's open. For each union date, daily return is close NAV after that date's fills divided by the previous union-date close NAV (or initial 1.0 on the first date), minus 1. The first day's return therefore includes buy costs and first-day market movement for any initial baseline purchases; do not prepend an extra zero return. Sharpe is arithmetic mean of these daily simple returns / population standard deviation (`ddof=0`) × `sqrt(252)`, risk-free rate 0. If standard deviation is zero or fewer than two daily returns exist, Sharpe is undefined.
- CAGR is `(terminal_NAV/1.0)^(365.25/calendar_days)-1`, where terminal NAV includes final liquidation costs. CAGR uses calendar days between first and last union date in the segment. MDD is peak-to-trough drawdown including initial NAV 1.0 and every daily close NAV, including terminal liquidation on the final observation. OOS calendar-year return starts at 1.0 in 2023; later years start at previous year-end NAV. Label the final partial year YTD through that market's final union date.
- Daily turnover uses the denominator defined above; total cost is cumulative transaction commission, tax, and modeled slippage in initial-NAV units. Record unfilled/expired events and terminal forced-liquidation costs.
- An exploratory relative pass requires OOS net CAGR and Sharpe both strictly above the same-cache B&H, and OOS MDD no worse than B&H, in both base and stress costs. Failure of any one condition is a screen failure. Passing this screen still does not imply an investable or valid index strategy.

## Rejection and interpretation

The two hypotheses are judged independently by the strict relative-pass rule above. No post-result utility tradeoff is permitted. Any conclusion is conditional on the fixed current-cache cohorts and adjusted-price series. This screen cannot validate index-wide generalization, future returns, data rights, corporate-action correctness, or real execution. Existing catalog entries named “gap” use close-to-close percentage change; this registration instead uses adjusted `Open_t/Close_(t-1)`. The different formula is why this is being considered as a separate exploratory mechanism, not a claim that the whole gap family is untested.

## Frozen hypothesis count

Two signal hypotheses × two markets = four signal-market hypotheses. Cost cases are sensitivity runs, not additional hypotheses. All missing/failed cases are retained in the report.
