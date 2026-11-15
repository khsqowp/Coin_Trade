# R004 — MACD zero-line cross with RSI(14) > 50

Status: preregistration amended before any performance metric was produced; first execution stopped on incomplete historical `markPrice` fields.

## Objective and lineage

- Hypothesis: on a completed USDT-M perpetual candle, a standard MACD(12,26) line crossing from `<= 0` to `> 0` while Wilder RSI(14) is strictly above 50 identifies a long entry whose cost- and funding-adjusted return can beat equal-capital buy-and-hold.
- This is the user's requested positive zero-line cross, not a MACD signal-line cross, not a MACD histogram flip, and not a short entry. The result cannot support a claim about short signals.
- Nearest prior work: paper strategy #6 used MACD(12,26,9) signal-line crossover with ATR exits; P9-C used a doji plus MACD-histogram sign flip. Those were related but not identical entry definitions. Their results remain unchanged.
- Four independently assigned review roles completed read-only reviews. They could not access the filesystem; their advice is treated as design caution, not repository verification. Lead inspection independently found the adjacent prior definitions above.

## Data and universe

- Price input: `/Users/user/CODE/Coin_Trade/chart_predictor/data/vision_dev_repaired.sqlite`, `candles` table, read-only.
- Six fixed symbols: BNBUSDT, BTCUSDT, DOGEUSDT, ETHUSDT, SOLUSDT, XRPUSDT. Common evaluation start is 2020-10-01 UTC, the first full common interval after SOL's recorded start; data end is exclusive 2026-07-01 UTC.
- The DB audit records 19,790,858 rows and no missing minutes or invalid OHLCV within observed symbol spans. It is a current six-symbol cohort, not a point-in-time futures-universe archive; survivorship and contract-history limits remain.
- Input full-file SHA-256 before analysis: `7780d5d4e174db4a55ccf7ecc81240e4138ce915a10f164dd22b35778d629914`.
- Candidate timeframes, UTC-aligned from 1m candles: 1m, 3m, 5m, 10m, 15m, 30m, 1h, 2h, 4h, 6h, 12h, 1d. Only complete aggregate bars are used.
- Public funding data, if successfully retrieved: Binance USDⓈ-M `GET /fapi/v1/fundingRate`, for the same six symbols and exact evaluation span. It is unauthenticated public market data; no account, API key, order endpoint, or trading action. The validation snapshot ID is `screen-through-2025-01-01`; the final snapshot ID is `final-through-2026-07-01`. Save raw response pages and hashes outside Git without overwriting the earlier snapshot. If coverage cannot be verified, label funding as incomplete and do not claim a fully cost-complete result.

## Frozen rules

- Indicators: use the repository's `chart_predictor.indicators` implementation unchanged. EMA(12) and EMA(26) are recursive with first-close seeding; MACD line is their difference. RSI and ATR use that module's Wilder-style EWM initialization. Signal line and histogram are not used.
- Signal anchor: only after candle close. Long trigger at bar `t` iff `MACD[t-1] <= 0`, `MACD[t] > 0`, and `RSI14[t] > 50`. Enter at the next timeframe bar's open. If another position for that symbol/exit variant is open, ignore the signal. No pyramiding, leverage, or shorting.
- Exit comparison (four predeclared alternatives; no result-driven refinement in this run):
  1. hard stop at 1.5 × ATR(14) below the entry, 2R take-profit;
  2. same stop, 3R take-profit;
  3. same stop, 4R take-profit;
  4. same hard stop, exit at the next bar open after a completed-bar MACD zero-line downward cross; no fixed target.
- All variants expire after 20 timeframe bars. A stop or target can trigger on the first touch. If both are touched within the same 1m bar, stop is assumed first. Gaps through the stop fill at the adverse open; target fills no better than its limit. Market exits use adverse slippage.
- Trade risk is set from ATR(14) known at the signal close; stop/target levels are fixed at entry. One symbol is one independent 1x sleeve; six sleeves start equal and cash is idle when flat. Report per-symbol and six-sleeve aggregate equity, not pooled trade-return sums.
- Costs: base 0.05% taker fee plus 0.02% adverse slippage per side; stress case doubles both. These are assumptions, not measured fills. Apply actual funding at timestamped settlements while a position is open; charge positive rates to longs and credit negative rates.
- Funding mark amendment (2026-11-16, before any performance metric was produced): raw public history contains blank `markPrice` for most early settlements. Preserve those rows and, only when `markPrice` is blank, use the symbol's most recent 1m candle open at or before settlement as a causal proxy; require it to be less than 60 seconds old. Never drop a funding settlement for this reason. The proxy is approximate rather than the exchange's actual mark; record the missing-mark fraction and label funding-adjusted metrics accordingly. If a qualifying prior 1m open is absent, stop the run rather than omit funding.
- Baseline: each symbol's 1x long buy-and-hold over the same split and dates, with equivalent entry/exit costs and observed funding. Report cash exposure and strategy/B&H drawdown separately.

## Splits and selection firewall

- Train: 2020-10-01 through 2024-01-01 UTC (end exclusive).
- Validation: 2024-01-01 through 2025-01-01 UTC (end exclusive). It may select at most one exit policy per timeframe using the frozen rule below.
- Final historical holdout: 2025-01-01 through 2026-07-01 UTC (end exclusive). It remains unopened until implementation, synthetic tests, code/data fingerprints, funding completeness, and the validation selection file are frozen. Each selected timeframe/exit is evaluated once. If prior use of any of this interval is discovered, it is downgraded to development and no sealed claim is made.
- Indicator warm-up may use only candles strictly before each signal. No position carries across split boundaries. Reject signals whose entry/maximum evaluation horizon would extend past that split's exclusive end.
- Validation selection: within each timeframe, select the single alternative with the highest validation net CAGR only if it beats that timeframe's matched B&H net CAGR, has positive net mean trade expectancy, at least 30 trades across the six sleeves, and no greater portfolio MDD than B&H. Ties break by lower turnover, then fixed rule order (2R, 3R, 4R, MACD-cross exit). Otherwise select no candidate for that timeframe.
- Final evidence: report net CAGR versus B&H, MDD, exposure, turnover, trade count, target-first rate where defined, quarterly excess returns, 95% block-bootstrap interval for mean daily excess, and Holm-adjusted one-sided p-value across at most 12 selected timeframe tests. No final re-tuning.

## Success, rejection, and limitations

- A timeframe is a *historical candidate only* if the selected policy has at least 30 final trades, beats B&H net CAGR in the final holdout, has positive net trade expectancy under base and doubled-cost assumptions, has no worse MDD than matched B&H, has positive B&H-relative return in a majority of the six final quarters, has a 95% block-bootstrap lower bound for mean daily excess above zero, and Holm-adjusted one-sided p < 0.05.
- A wider project-level `80%` selective-signal claim is not eligible from this database: it has only six current symbols (the product contract calls for at least 20 symbols for a qualifying sealed claim), and no point-in-time universe. Report target-first rate and Wilson interval descriptively; do not call it qualified.
- Maximum acceptable drawdown has not been set. No autonomous or live-use recommendation can be made. This is 1x historical research only.
- If a candidate fails, record the failure and do not tweak thresholds or exits using the final holdout. Any new strategy-family iteration must have a materially different hypothesis and new preregistration.

## Required artifacts and verification

- `plan.md`, `manifest.json`, `results.json`, `decision.md`, `handoff.md`; reproducible experiment code and synthetic unit tests.
- Record exact command, environment, code SHA-256, price DB SHA-256, funding raw-page hashes/coverage, counts of all entry signals/trades/exits, split boundaries, all 48 screening cells, excluded/error cells, metrics, confidence intervals, and decision.
- Before price analysis: run only synthetic unit tests and confirm read-only SQLite access. Do not modify the source checkout or its existing trial registry. Store this run's outputs and any downloaded raw funding data in the isolated temporary worktree's ignored `chart_predictor/data/strategy_lab/2026-11-16-r004-macd-zero-rsi50/` directory; commit reports/code, never market-data databases.

## Execution amendment log

- First screen attempt (2026-11-16) failed while parsing the first blank historical `markPrice`; it produced no screen JSON or performance metrics. The price reader had opened the read-only database and loaded the first symbol's candle rows before failure, so the original blanket statement that no price rows were read is superseded. No source DB or trial registry was changed.
- Second attempt failed because funding timestamps can have millisecond jitter relative to minute boundaries; it produced no screen JSON or performance metrics. The loader now uses the most recent prior minute open, with a strict one-minute staleness guard, only for blank mark prices. Added synthetic coverage for jittered timestamps, blank and present mark fields.
- After the first successful screen, source review found the selector omitted the preregistered 30-trade minimum. The selector is corrected to enforce that already-frozen rule and now has a boundary regression test; final screening must be rerun with the corrected selector and new hashes. This is an implementation correction, not a threshold change.
