# MACD zero-cross + RSI 50 long strategy preregistration — 2026-11-15

## Question and status

Hypothesis: after a completed 5-minute candle closes with the MACD(12,26,9) line crossing from non-positive to positive and RSI(14) above 50, a long entered at the next 5-minute open has positive net expectancy; a small set of rule-based exits may improve on holding the same entry to the fixed time limit.

This is one targeted strategy test and four economically distinct exit candidates, not a general indicator grid. The late-period segment is a chronological holdout for this experiment only. The broader project has already examined the same calendar window, so this is not an untouched/sealed project evaluation and cannot satisfy the final 80% signal gate.

## Data and universe

- Source: existing local Binance USDⓈ-M 1-minute OHLCV SQLite database, opened read-only. No exchange calls or credentials.
- Symbols: BTCUSDT and ETHUSDT only, fixed before measuring strategy results. Results are not claimed to generalize to altcoins.
- Input window: 2026-07-17 00:00 UTC inclusive to 2026-10-09 00:00 UTC exclusive, the existing 84-day research development window.
- Bars: aggregate complete 1-minute rows into UTC-aligned 5-minute bars. Incomplete 5-minute buckets and any missing 1-minute interval are excluded; an unexplained gap invalidates affected trades.
- Split: first 70% of the 84-day calendar window for exit selection (through 2026-09-13 19:12 UTC); final 30% for one conditional temporal holdout. Purge training entries whose 20-bar maximum exit would cross the split. Indicators use only past and current completed 5-minute closes.

## Frozen entry and trade accounting

1. On completed bar `i`, MACD line crosses zero upward: `MACD[i-1] <= 0` and `MACD[i] > 0`.
2. On that same completed bar, RSI(14) is strictly greater than 50.
3. Enter long at the next 5-minute bar open. Do not enter if the next open is absent or the path to the fixed 20-bar timeout is incomplete.
4. ATR(14) on the signal bar defines initial risk as `2 × ATR`; the protective stop is entry minus that distance. Maximum holding is 20 bars (100 minutes). All strategies use the same signal anchors and suppress a new entry until the 20-bar horizon has elapsed, even if a selected exit closes earlier. This keeps exit comparisons paired and non-overlapping.
5. Stop and target are checked on 1-minute OHLC. If stop and target are both touched in the same 1-minute candle, stop wins. A stop gap fills at the 1-minute open when worse than the stop price; a target fills no better than its stated limit. MACD/RSI close signals execute at the next 5-minute open, after checking any protective stop gap at that open. Timeout exits at the 20th following 5-minute open.
6. Fees: base 0.10% round-trip (0.05% per side), matching the project convention. Stress case: 0.20% round-trip. Slippage, spread, market impact, funding, and liquidation are not in the source DB and are not imputed; a positive result is therefore not execution validation.

## Exit candidates (four; no parameter sweep)

All candidates share the same 2-ATR initial stop and 20-bar maximum hold. The no-profit-rule 20-bar time exit is the paired baseline.

- `macd_zero_down`: exit at next 5-minute open after completed MACD line crosses from non-negative to negative.
- `rsi_below_50`: exit at next 5-minute open after completed RSI(14) crosses from at/above 50 to below 50.
- `fixed_2R`: limit take-profit at 2R from entry; stop-first same-minute tie.
- `chandelier_3ATR`: ratcheting stop at the greater of the initial stop and prior completed-bar high-water mark minus 3×ATR(14), active from the next bar. No separate profit target.

The 2-ATR stop, 2R target, 3-ATR trail, 5-minute timeframe, and 20-bar timeout are fixed reference choices informed by the current project’s 5-minute/50–100-minute horizon and common volatility-normalized exit designs. They are not presumed optimal. The external exit-rule literature reports conditional, market-specific results, so its values are experimental anchors, not transferred evidence.

## Selection and stop rules

- On the first 70% only, select the candidate with the highest mean net R among candidates with at least 30 trades, positive mean net R, and profit factor above 1.0. Fixed tie order: `macd_zero_down`, `rsi_below_50`, `fixed_2R`, `chandelier_3ATR`.
- If no candidate meets all three conditions, stop: record no exit selected and do not inspect the final 30% strategy outcomes.
- If one candidate qualifies, freeze its code/rules and evaluate only that candidate and the paired 20-bar baseline on the final 30%, at base and stress fees. Do not retune after seeing the holdout.
- Report trade count, net-positive trade rate and Wilson 95% interval, mean/median net R, profit factor, average hold, exit reasons, symbol-level results, and a paired UTC-day block-bootstrap interval for the mean net-R difference versus the time-exit baseline. This is exploratory evidence, not the project’s M4 target-first accuracy.
- Do not claim an 80% success. The final project gate still requires a separate one-time forward evaluation with at least 200 selected non-overlapping events across at least 20 symbols, at least 10% coverage, a 95% lower bound above matched baselines, and positive cost-adjusted expectancy.

## Causal and quality checks

- Verify MACD, RSI, ATR, and entry timestamps are prefix-invariant when later candles are appended or mutated.
- Independently hand-check at least one synthetic trade per exit type, including next-open entry, a stop/target same-minute tie, a stop gap, and signal/timeout precedence.
- Validate exact 1-minute continuity for both symbols and ensure every 5-minute bar is built from five distinct constituent minutes.
- Record the input database path only in the local run command; never include a personal absolute path in committed artifacts. Store code revision and data-window counts in the report, but do not hash/read sealed rows.

## Rationale references

- Hudson & Urquhart (2019), *Technical trading and cryptocurrencies*, motivates explicit transaction-cost accounting and cautions against assuming one rule generalizes across coins: https://centaur.reading.ac.uk/85715/8/Hudson-Urquhart2019_Article_TechnicalTradingAndCryptocurre.pdf
- A 2026 ATR-exit study combines MACD with volatility-scaled exits on daily USD/JPY and reports context-dependent results; it motivates testing exit families but is not evidence for crypto or these parameter values: https://www.mdpi.com/1911-8074/19/8/554
