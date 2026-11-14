# Research round 3: small-capital long-only rotation (capital 128.88 USDT, 1x, backtest only)
Protocol: `research/PREREG_round3.md` (written and hashed BEFORE any rotation backtest). Code: `tp.rotation` (simulator), `tp.rotstudy` (study), `tp.rotfetch` (public data). Results: `runs/research/r3_rotation_*.json`.
Reproduce: `./run.sh data rot-fetch` (public GET only) then `./run.sh research rot-study --part main|cost|lev|phase|filters` (offline, niced).
Window: 2024-12-18 to 2026-10-25 (16,219 hourly bars after a 1,300-bar warm-up), 25 USDT-M perpetuals. Costs: taker 0.05% + slippage 0.02% per side, real funding. 66 selection trials logged (64 rotation variants + 2 reference-rule variants).

## Bottom line
No variant passes the pre-registered forward rule or the numeric gate. Every one of the 66 variants has a maximum drawdown above the 35% gate limit (best 50.7%); the best deflated Sharpe is 0.31 (needs >= 0.90).
Return paths depend heavily on the rebalance phase (same rule, start 2 h or 12 h later: Sharpe 1.39 -> -0.02), so the attractive-looking variants are not stable. Nothing was added to the forward tracker. The result is poor and is reported as poor.

## Benchmarks (same window, same costs)
| benchmark | Sharpe | Sharpe 1st half | Sharpe 2nd half | total return | max drawdown |
|---|---|---|---|---|---|
| BTC hold (1x, funding paid) | -0.20 | -0.38 | 0.03 | -28.8% | 54.5% |
| ETH hold | -0.14 | -0.19 | -0.03 | -43.4% | 69.7% |
| universe equal weight, daily rebalanced (idealised, no minNotional) | 0.26 | -0.13 | 0.82 | -13.3% | 62.8% |
| reference rule (owner's repo card, LONG LEG ONLY) top-8 / 14d / 3-day rebalance / BTC crash filter | 0.50 | 0.73 | 0.27 | +21.0% | 61.6% |
| same, top-3 | 0.74 | 1.34 | 0.26 | +42.5% | 79.4% |
The reference rule is dollar-neutral long/short in the owner's repo; only the long leg is reproducible with a 1x long-only account, so its numbers are not comparable with the repo's own results. With K = 8 each slot is 16 USDT: BTC and ETH orders were rejected (minNotional 50 / 20 USDT) 115 / 112 times.

## Fixed vs adaptive clock, all-in vs split (64 variants; medians over the 16 variants of each clock)
| clock | median Sharpe | best Sharpe | median trades | fees (USDT) | slippage (USDT) | funding paid (USDT, negative = received) | share of variants with total return > 0 | median MDD |
|---|---|---|---|---|---|---|---|---|
| 1h fixed | 0.155 | 1.18 | 255 | 12.7 | 5.1 | -7.1 | 19% | 86.7% |
| 4h fixed | -0.097 | 1.22 | 125 | 6.0 | 2.4 | -4.3 | 12% | 89.3% |
| 1d fixed | 0.071 | 1.39 | 56 | 2.7 | 1.1 | -9.7 | 25% | 84.9% |
| adaptive (BTC regime: high_vol->1h, trend->4h, range->1d) | -0.138 | 0.77 | 86 | 3.5 | 1.4 | -7.6 | 12% | 88.4% |
Adaptive spent 57% of the time on the 1h clock, 24% on 4h, 19% on 1d. H2 (adaptive >= best fixed) was NOT supported: adaptive is not better than any fixed clock. Turnover costs rise with faster clocks (1h clock: fees plus slippage = 13.8% of the starting capital over the window, 1d: 2.9%), but net Sharpe is not monotonic in turnover, so H3 holds only for the cost line.
| positions | median Sharpe | median MDD | median total return | variants with return > 0 | variants losing > 80% |
|---|---|---|---|---|---|
| all-in (n=1) | -0.195 | 93.5% | -84.3% | 3% | 53% |
| 3-way split (n=3) | 0.161 | 81.7% | -47.4% | 31% | 22% |
Stops: median Sharpe trail10 -0.43, atr3 +0.16, down4 +0.05, loss7 -0.28. BTC filter on: median Sharpe +0.21 (return -41%), off: -0.29 (return -89%). The fixed 7% loss limit has no profit exit by design, so its closed trades are all losses and winners stay open; it is the weakest rule structurally.

## Strict out-of-sample and multiple testing
Variant chosen by first-half Sharpe, evaluated on the second half: all-in pick `c1d_n1_atr3_b0` 1.47 -> 0.68; split pick `c1d_n3_atr3_b1` 1.46 -> 1.31 (BTC hold second half 0.03, equal weight 0.82). The best hindsight second-half Sharpe among split variants was 2.50.
Deflated Sharpe over 66 trials (null variance / robust empirical variance): best 0.31 / 0.37 (`c1d_n3_atr3_b1`); 0 of 66 reach 0.90. The survivorship bias (below) pushes in the optimistic direction, so the true figures are lower.
Best variant `c1d_n3_atr3_b1` (3 positions, daily clock, ATR trail, BTC filter): +306% (128.88 -> 523.06 USDT), MDD 50.7%, 85 trades, fees 5.8 + slippage 2.3 USDT, funding received 13.2, worst 30 days -31%. Rebalance phase +12 h: Sharpe -0.02, return -37.9%.
Start-phase sensitivity (32 variants on the 4h / 1d clocks shifted by 2 h / 12 h): median Sharpe change +0.36, range -1.41 to +1.88, sign of Sharpe flipped for 17 of 32. Results are mostly a draw of the phase, the same effect the source repo reports.

## Drawdown distribution and worst cases (block bootstrap of 100 consecutive trades, 2,000 sequences)
| variant | trades | win rate | worst trade | longest losing streak | bootstrap MDD P50 / P95 / P99 / max |
|---|---|---|---|---|---|
| all-in, first-half pick (`c1d_n1_atr3_b0`) | 26 | 19% | -37.4% | 12 | 99.8% / 100% / 100% / 100% |
| all-in, median-Sharpe variant | 34 | 0% (closed trades) | -29.7% | 34 | 100% |
| split, first-half pick (`c1d_n3_atr3_b1`) | 85 | 36.5% | -16.0% | 9 | 42% / 65% / 75% / 85% |
| split, median-Sharpe variant | 85 | 23.5% | -20.7% | 14 | 91% / 98% / 99% / 100% |
Realised worst 30-day return of the all-in pick: -72%; of the split pick: -31%. With the full account in one symbol and a stop-then-reinvest cycle, a drawdown of 90% or more is the median outcome among the variants tested, not a tail event.
Inherited RiskConfig limits (daily loss 3%, drawdown halt 15%, 10 trades per day) would have been breached: the split pick had 80 days with a daily loss above 3%, the all-in pick 197; days with more than 10 fills were rare (0-1).

## Gate result (profile `crypto_small_rotation`: only the position cap is 100%; all other limits inherited)
`gate_numeric` passes 0 of 66. Reasons: max drawdown above 35% (66), second-half Sharpe below 0.5 (48), OOS degradation versus the first half (21), too few trades (3), too few OOS trades (1). Look-ahead check: every variant reproduced its own first-half equity when the run was cut at the midpoint (66 of 66).

## Leverage sensitivity (selection = 0, isolated margin, liquidation modelled, mmr 0.5%)
2x: median Sharpe -0.48, median MDD 98.5%, 12 of 64 variants liquidated at least once (16 liquidations), 77% of variants lost more than 90%. 3x: median Sharpe -0.58, 39 of 64 variants liquidated (62 liquidations), 88% lost more than 90%.
The best split variant: 2x +392% with MDD 74.5%; 3x +131% with MDD 87.6% and 3 liquidations. Leverage multiplies the drawdown problem; it is shown for information only.

## Cost sensitivity
Slippage 0.01% / 0.05% and a 50% maker mix change the median Sharpe by less than 0.01 and the picks by less than 0.03: at 128.88 USDT absolute fees are a few USDT, and the dominant uncertainty is the price path and the rebalance phase, not the fee tier.

## Effect of the small-account constraints (exchange filters from public exchangeInfo, assumed constant)
* Minimum notional: BTCUSDT 50 USDT, ETHUSDT 20 USDT, others 5 USDT. With 3 slots of 43 USDT BTC cannot be bought at the start (rejected 5-34 times in the leading variants); K = 8 cannot hold BTC/ETH at all.
* Equity decay: once an all-in account falls below 5 USDT every order is rejected (82,605 rejected orders over the 64 variants, mostly in ruined accounts). With all filters removed (minNotional 0, tiny step) the median Sharpe moves from -0.038 to +0.039 and the leading variants by less than 0.13 (best split variant 1.39 -> 1.37; `c4h_n3_loss7_b1` 1.22 -> 1.34). The filters matter at the margin, not for the conclusion.
* Step sizes are coarse for 1-unit coins (the quantity is floored), which shows up as small cash residues, not as a result driver.

## Limits and honest caveats
* Survivorship bias cannot be removed with public data: the universe is today's top-24h-volume list (it contains several recent listings with hype volume: BIRB, APR, MAGMA, JCT, IRYS, ORDER) and delisted losers are absent. The equal-weight benchmark of the same universe is still -13%, but momentum picks inside a pre-selected winners list are optimistic. Point-in-time liquidity and a 30-day history requirement only partly offset this.
* Only 22 months of data, one market phase (falling BTC). 66 variants were tried; none is distinguishable from luck after deflation.
* Filters and fees are today's values. 24 symbols instead of the pre-registered "top 25 plus BTC and ETH" (BTC and ETH were part of the 25).
* Pre-registration typo: H4 text contains a stray question mark; the rules themselves were not changed.
Owner questions raised by this result: see the final report.
