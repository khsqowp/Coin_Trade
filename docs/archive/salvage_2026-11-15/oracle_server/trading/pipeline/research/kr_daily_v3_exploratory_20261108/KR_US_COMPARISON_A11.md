# KR-US A11 Exploratory Strategy Comparison
Recorded 2026-11-08 KST. Research only; PASS_EXPLORATORY_ONLY.
Matched reused OOS: 2020-01-01..2026-08-18. Liquidity universe = lagged 60-session median traded value Top50/100/200, not market cap; K20, nominal 5% each. Returns are local currency. US cost 10bp/side; KR fee/tax plus liquidity-tier slippage differ.

## Matched OOS Top50
| Portfolio | CAGR | Sharpe | MDD |
|---|---:|---:|---:|
| KR KODEX200 | 24.81% | 0.889 | -40.81% |
| KR equal weight | 7.05% | 0.377 | -54.78% |
| KR residual momentum | 13.48% | 0.528 | -59.85% |
| KR RSI2 mean reversion | 3.12% | 0.257 | -25.29% |
| KR gap reversal | -9.37% | -0.542 | -53.79% |
| US SPY buy-and-hold | 15.67% | 0.822 | -33.72% |
| US equal weight | 18.69% | 0.875 | -31.69% |
| US residual momentum | 24.22% | 0.987 | -29.20% |
| US RSI2 mean reversion | 7.40% | 0.735 | -10.20% |
| US gap reversal | -0.63% | -0.024 | -19.88% |

## Residual momentum TopN
| Market | N | CAGR | Sharpe | MDD |
|---|---:|---:|---:|---:|
| KR | 50 | 13.48% | 0.528 | -59.85% |
| KR | 100 | -7.64% | -0.016 | -77.24% |
| KR | 200 | -30.45% | -0.685 | -94.83% |
| US | 50 | 24.22% | 0.987 | -29.20% |
| US | 100 | 22.81% | 0.899 | -34.83% |
| US | 200 | 14.30% | 0.620 | -37.40% |

## Findings and boundary
KR residual Top50 beat KR equal-weight CAGR by 6.43pp but trailed KODEX200 by 11.33pp and had ~60% drawdown; KR full-sample CAGR was about -0.98%. US residual Top50 was strongest in this previously inspected OOS, but membership data are incomplete. Wider KR universe worsened results. RSI2 drawdowns were smaller but returns lagged market references; gap reversal was negative KR and near-flat US. No validated winner is established.
Coin_Trade overlap: RSI2 and gap/short-term reversal overlap its RSI2/reversal catalog. Residual momentum is adjacent to its momentum/residual family; this exact 126-session beta-residual setup is a different configuration, not a new family.

## QC
Run KR-V3-EXPLORATORY-20261108T075447Z exited 0. POSTRUN_VERIFY_A11.json reports PASS_EXPLORATORY_ONLY, 13/13 cells, 13/13 aligned records, 2,906 finite numeric leaves, 3,541 NAV rows, 65 summaries.
KR: 3,236 parquet series, 651 confirmed delisted, 108 unresolved early-ending; fetch errors 010040/144740/463480; listed zero-row 495910. 1,122 post-repair jumps across 357 symbols were classified as confirmed delisted terminal 15-bar events. This does not prove terminal fills/marks correct. No unresolved early-ending names in Top50 strategy positions at cutoff; EW Top100 had 1 and Top200 had 3. Missing names can alter historical liquidity membership.
US: 1,209 PIT tickers/1,262 membership spells; 492 lacked parquet; 678 loaded after exclusions. S&P membership archive is manually assembled/incomplete and ends 2026-08-18. Corporate actions, terminal liquidation, point-in-time membership, costs/capacity and FX are not fully closed. This OOS was already inspected and is contaminated/reused, not a fresh holdout.

## Next stage (not run)
First bound KR missing-symbol/top-N effects and delisted terminal-price/PnL sensitivity; do not start a 48-cell grid until this data check is complete. Keep v2 immutable; any retries go to separate supplement with manifest/hashes. For a later pre-registered exploratory grid, use residual momentum variants 126d no skip; 126d+21-session skip; 252d+21-session skip; 126d gated by benchmark SMA200 (t-1), Top50/100/200, K20, base and 2x costs, common month-end rebalance/next-open execution, every cell reported. Reused OOS cannot validate/promote a winner; require untouched history or forward paper evidence.

## Hashes
run_v3.py 2e8cd2f7f7bb77cacca2d77e3f6f42564184c359d8d447f62116e6095f5cfc76
engine_v2copy.py 0ba6201ae243ca94ff032cd06b6ca8a42e8fb66b7ccc4d67339c8fcb434ad38c
A11.json 1229c6c7f07947dafdf32531a56bc161a2f415aef5c115967bc5f740ea26b278
results.json d9faff875c9f6f1549c62a805defafe2f07947b32fbd88fa386b2e0bc3479b90
aligned_results.json 137efe82c79cb74e3b1241b2f5b421fe39c7019f9ef56c33fe2c64a9a220a385

## A12 precheck (read-only, 2026-11-08)
Universe dates for the four non-parquet cases were checked against the frozen KR raw universe:
- 010040 한국내화 is listed since 2000-10-16; missing long history can affect liquidity membership, impact unknown without prices.
- 144740 피엠디아카데미 delisted 2018-08-07; its missing 2011-2018 series can affect historical Top-N ranks, impact unknown.
- 463480 모티브링크 listed 2025-02-20; potentially eligible by the 2026-08-18 aligned cutoff, impact unknown.
- 495910 이에스티 listed 2026-11-04, after both the KR evaluation end (2026-11-03) and aligned cutoff; no effect on these study windows.
The fetch container kr2fetch was not present at inspection time, so no retry was attempted and no source data changed.
A11 results record one terminal liquidation for residual Top50, zero for residual Top100/200, and three for equal-weight Top50. The simulator applies last-close proxy and sell costs, but the result JSON records only terminal liquidation counts, not a per-event terminal PnL attribution. This decomposition is still required before the proposed grid.
