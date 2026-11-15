# R004 decision — MACD zero-line cross + RSI(14) > 50

## Decision

**Reject for now; do not open the final holdout.** No validation timeframe/exit combination passed the frozen selection gate. In particular, none of the 48 validation aggregate cells beat matched buy-and-hold net CAGR, so the code selected zero candidates. The final 2025-01-01–2026-07-01 interval was not read by this run.

## What was tested

- Six fixed USDⓈ-M perpetual symbols: BNBUSDT, BTCUSDT, DOGEUSDT, ETHUSDT, SOLUSDT, XRPUSDT.
- Twelve complete-bar timeframes from 1 minute through 1 day; four exit choices: 2R, 3R, 4R targets, or MACD zero-line downward cross. Each uses a 1.5×ATR(14) stop and a 20-bar maximum holding period.
- Long entry only: completed-bar MACD(12,26) crosses from non-positive to positive while RSI(14)>50; entry at next timeframe bar open.
- Train: 2020-10-01–2024-01-01. Validation: 2024-01-01–2025-01-01. Six equal 1× sleeves; no leverage, shorting, pyramiding, or live orders.
- Base assumptions: 0.05% taker fee and 0.02% adverse slippage per side; stress doubles both. Public timestamped funding rates were applied.

## Validation findings

- Passed the buy-and-hold CAGR gate: **0 / 48** cells.
- Passed positive mean net trade expectancy: 21 / 48 cells.
- Passed maximum-drawdown no-worse-than-buy-and-hold: 24 / 48 cells.
- All 48 cells had at least 30 aggregate trades. The selector now explicitly enforces this preregistered minimum and is covered by a boundary test.
- Matched 1× buy-and-hold validation CAGR was 127.07% for this 2024 interval. This unusually strong interval benchmark is a material context, not evidence that buy-and-hold will repeat.
- Best validation CAGR among the tested cells was daily bars + MACD-down-cross exit: +40.02% versus +127.07% for buy-and-hold; 33 trades, 9.57% mean net trade, 18.35% strategy MDD versus 38.56% buy-and-hold MDD. It still fails the frozen return gate.
- The next-highest cell was 6-hour bars + MACD-down-cross exit: +23.67% versus +127.07% buy-and-hold, 151 trades, 1.07% mean net trade, and 12.56% MDD. It also fails the return gate.
- At 1–30 minute bars, every cell had negative net CAGR, negative average net trade, and materially worse drawdown than the matched benchmark in the best cell for each timeframe. A higher trade win rate in some target policies did not offset losses and costs.
- Under doubled costs, the best 6-hour MACD-down-cross cell remained positive (+19.35% CAGR; +0.93% mean net trade), but remained far below buy-and-hold. This does not qualify it for holdout selection.

## Data and interpretation limits

- The public funding endpoint returned blank `markPrice` on 3,376 of 4,659 records for five symbols (72.46%), and 3,451 of 4,734 SOL records (72.90%). The frozen amendment uses the most recent prior 1-minute candle open, less than 60 seconds old, as a causal proxy only for those blank marks. Therefore funding-adjusted figures are approximate, not exact exchange-mark accounting.
- Funding history had no duplicate timestamps; maximum observed gap was about 8 hours, within the stated 24-hour coverage check. Raw pages and their hashes are retained outside Git.
- The price database is a six-symbol current cohort, not a point-in-time futures universe. Survivorship/contract-history bias remains. This study cannot establish broad 80% signal accuracy.
- The final holdout was not opened because validation selected no candidate. No statistical claim or live-use recommendation is made. Maximum acceptable drawdown is still unspecified.
- Two independent attempts stopped before metrics because of blank funding mark fields and millisecond timestamp jitter. The loader was amended and synthetic tests cover these cases. A separate code review then found and fixed the missing preregistered 30-trade selection gate; the final screen was rerun with the corrected implementation.

## Reproducibility

- Machine-readable report: `results.json` contains all 96 aggregate train/validation cells; verbose daily-return vectors are excluded. `symbol_results.json.gz` contains all 576 per-symbol split summaries. The full ignored screen output remains in the isolated worktree.
- Full screen output SHA-256: `05fe3b3cd1536f02c29d8501101ba2c33e802e6df8627e2a97967aa4cdb7951f`.
- Price DB SHA-256: `7780d5d4e174db4a55ccf7ecc81240e4138ce915a10f164dd22b35778d629914`.
- Final runner SHA-256: `81d039203428f796ea68c8fc73a630e2b5d4f0a3588c5df83d0192ca657f20d6`.
- Synthetic tests: 10 passed. The source checkout and its prior trial registry were not modified. No order/account API was used.
