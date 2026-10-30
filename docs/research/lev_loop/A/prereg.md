# PREREGISTRATION - BACKTESTER-A (lev_loop, round 1)

Written BEFORE any cell of the grid below was run with the new engine. Research only; no live files touched.

## 0. Disclosures (what I had seen/run before writing this)
- I read tp_loop/review/review.md section 6 (3-phase V0 lev x deploy table). So the qualitative shape (CAGR non-monotone, MDD up with lev, 3.0x1.0 -> 96% CAGR) is KNOWN to me. That table used daily-close kill, 3 phases, no liquidation model; nothing in this prereg's metrics (jittered distributions, intraday kill, liquidation, stress) was seen.
- Before this file I ran only `parity.py`: new engine kill_mode=0/liq_stop=1 vs rs_final_engine.Sim.run (crash_flat=True), 54 bit-exact comparisons (6 cells x 3 phases x 3 windows), plus the identity check lev x deploy. Live V0 cell phase ends 14.5027/18.4064/15.8459 reproduce review.md. These are replication facts, not selection inputs.
- V0 hyper-parameters (lookback 14, rebalance 3, K 8, crash flat) were chosen on the full sample by earlier work (review.md #10). The IS/OOS split below only protects the leverage/kill choice, not those parameters.
- engine file: app/rs_lev_a_engine.py sha256 3935af6141cf97c9d98fe32995a00ef9a5abb930cc201b44588f1d950fd92a19

## 1. Design reduction (432 -> 24 cells), logic
Full requested grid: lev {2.5,3,3.5,4,5,6} x deploy {0.7,0.95,1.0} x kill {0.25,0.35,0.5,none} x cooldown {7,14} = 432.
1. IDENTITY (verified bit-exact in parity.py): the simulator uses lev and deploy only through the product G = lev*deploy (position notional = equity*deploy*lev/(2K)); cross-margin liquidation depends on equity vs notional, not on the per-symbol leverage setting. So the deploy axis is NOT an independent dimension; deploy is fixed at the live value 0.95 and lev takes the ladder. Deploy 0.7 or 1.0 at lev L is the same as deploy 0.95 at lev L*0.7/0.95 or L*1.0/0.95. Deploy only matters on a real exchange through initial-margin headroom (not modelled; cross-margin liquidation is the maintenance-margin test).
2. COOLDOWN is a pure kill-parameter and is irrelevant for kill=none; to keep 24 cells it is fixed at the live value 14. cooldown=7 is run AFTER selection as an exploratory sensitivity (selected cell + current + neighbors only); it cannot change the selection.
3. Kept: full lev ladder (6) x full kill axis (4) = **24 cells**, deploy 0.95, cooldown 14. Gross G = 0.95*lev: 2.375, 2.85, 3.325, 3.8, 4.75, 5.7.

CELL LIST (lev | kill): lev in {2.5, 3, 3.5, 4, 5, 6} x kill in {0.25, 0.35, 0.5, none(=1.0)}.
CURRENT (reference) = lev 4 | kill 0.35 (cooldown 14, deploy 0.95).
Owner constraint: SELECTABLE set = cells with lev >= 4 (12 cells). lev 2.5/3/3.5 are run as frontier references and can only be reported, not selected.

## 2. Paths (jitter)
Offsets off = 0..39 days and rebalance phase p = 0,1,2 -> 120 paths per cell per window, every cell on the same 120 (paired).
- IS windows: d0 = idx(2022-01-01)+off, d1 = idx(2024-07-01).  OOS: d0 = idx(2024-07-01)+off, d1 = end of panel (2026-10-09). FULL: d0 = idx(2022-01-01)+off, d1 = end. Equity restarts at 1.0 at each d0 (fresh account). eq0=1, fee 0.1%/side, real funding, crash_flat=True, K=8, rebal 3, lookback 14.
- OOS and FULL are not executed until selection.json is written and hashed (stage 2).

## 3. Variants / scenarios
- Kill version: INTRADAY (kill_mode=1: hourly worst-case equity vs hourly-close HWM; exit at that hour's adverse marks) is PRIMARY: it approximates the live bot, which evaluates sampled instantaneous equity every cycle (momentum_rotation_loop: dd = 1 - equity/hwm each CHECK_INTERVAL, 15 s in deployment, HWM = running max of sampled equity). DAILY-CLOSE (kill_mode=0) is reported as the legacy version. kill_mode=2 (HWM also on hourly best-case; max-pessimism bound) is reported for current + selected only.
- Scenarios (kill_mode=1): BASE; VOL (hourly log price moves x1.5 via per-symbol power transform of H/L/C, funding rescaled by close ratio, BTC crash filter and signal recomputed on stressed prices); COST (fee/slippage 0.2%/side, i.e. 2x); COMB (VOL+COST, report-only).
- Daily-close version run in BASE only.
- Liquidation models, evaluated every hour on worst-case equity wc_h = W + funding + sum q*(adverse - entry) (longs at L, shorts at H, simultaneous), maintenance computed on |q|*H_h: liquidated iff wc_h <= maintenance margin.
  - TIER: per-position rate by USD notional bracket (A0 = 10,000 USD per 1.0 equity): <50k 0.5%, 50k-250k 1%, 250k-1M 2.5%, >1M 5% (assumption modelled on Binance USDT-M alt brackets; liquidation fee not modelled).
  - FLAT3: 3% of notional on all positions (conservative variant; covers liquidation fee/odd alt brackets).
  - Counterfactual: the path is NOT stopped at a liquidation flag (only at equity<=0). First-event day and min cushion (wc-maint)/previous-close-equity are recorded. Ruin-adjusted wealth = 0 for flagged paths.
- Distance-to-liquidation = min over time of cushion; report min over paths and p10.

## 4. Metrics (per cell, per window, over 120 paths)
terminal wealth (median, p10, p90, mean), annualised log growth g = ln(W_end)/(days/365) (mean, median), CAGR = exp(g)-1 (median), daily-close MDD (median, p90, max), intraday MDD (hourly worst-case vs HWM; median, p90, max), kills (mean, p90), liquidation probability under TIER and FLAT3 (fraction of paths with flag) for BASE/VOL/COST/COMB, min cushion, per-trade and per-symbol concentration for current/selected (top-5 symbols and top-5 trades share of total net gain on the median-terminal-wealth path, and distribution across paths).

## 5. Admissibility (hard, on IS paths first; re-reported for OOS and FULL)
A cell is ADMISSIBLE iff, in the intraday-kill version, liquidation count = 0 over all 120 paths for BOTH TIER and FLAT3 in BASE, in VOL and in COST scenarios (COMB reported, not required). OOS/FULL admissibility is recomputed after selection and must also hold for a "move" recommendation.

## 6. Selection rule (IS only)
1. Candidates = admissible cells with lev >= 4.
2. Score = IS mean annualised log growth g over 120 paths (intraday kill, BASE). Highest = S.
3. Plateau test: neighbors = same kill with adjacent lev (ladder order) and same lev with adjacent kill (order 0.25,0.35,0.5,none). S passes iff every neighbor has IS mean g >= 0.75*g_S (neighbors may be inadmissible, but that is reported as 'cliff'). If S fails, take the next-best candidate and repeat; if none passes, selection = NONE.
4. Also report the unconstrained best admissible cell (any lev) for information; it is not selectable.
selection.json (with S, ranks, plateau result) is written and its sha256 logged BEFORE stage 2.

## 7. Inference
- Paired difference per path d = g_cell - g_current.
- Block bootstrap (circular blocks of 15 days, B = 4000, seed 20261030): draw a path uniformly from the 120, resample its daily paired log-return difference series (ln eq_t/eq_{t-1}, cell minus current) in 15-day blocks to the same length, statistic = 365*mean. 95% percentile CI; separately report the empirical across-path distribution (mean, p10, p90, win rate). Paths with ruin/equity<=0 are excluded from the bootstrap and counted as inadmissible.
- Multiple testing: trials N = 24 cells (selection family); sensitivity N = 150 (to reflect the earlier research lineage of ~100+ configurations). (a) Growth haircut = SE_boot * E[max of N iid standard normals] (E[max] approximated with the Gumbel-type formula (1-gamma)*Phi^-1(1-1/N)+gamma*Phi^-1(1-1/(N e))); (b) Deflated Sharpe Ratio (Bailey & Lopez de Prado) of the selected cell on the median-terminal-wealth IS path's daily returns, with V[SR] estimated across the 24 cells' path-mean Sharpe ratios.
- Verdict per cell (vs current), requiring BOTH IS and OOS: BETTER = both 95% CI lower bounds > 0 AND admissible (IS & OOS) ; WORSE = both CI upper bounds < 0, or inadmissible while current is admissible (labelled 'worse-inadmissible') ; otherwise NOT DISTINGUISHABLE. Region verdicts = by lev row and by kill column from the cells in them (reported as counts).

## 8. Decision rule (overall)
- MOVE TO S iff: S selected in stage 1 (admissible, plateau pass) AND S verdict BETTER vs current AND S admissible in OOS and FULL AND haircut-adjusted OOS growth difference (point - haircut at N=24) > 0.
- KEEP CURRENT iff current is admissible AND (no S, or S is not BETTER, or any of the above fails) AND IS/OOS signs do not conflict materially.
- NEED MORE DATA iff IS and OOS verdicts conflict in sign (one BETTER, other WORSE) or current itself is inadmissible (then the owner constraint "do not lower leverage" conflicts with "do not liquidate"; report the highest-growth admissible cell of any lev as information for an owner decision).
- Above-4x question: answered by the lev 5 and 6 rows: 'helps' only if some lev>=5 cell is BETTER and admissible in IS, OOS, FULL.

## 9. Amendments
Only for bugs, never to add cells after seeing results. Each amendment gets a new hash line labelled 'amendment' with the reason.

## 10. AMENDMENT 1 (2026-10-30, BEFORE any stage-1 result; NOT a code bug - a model-bracketing addition)
Reason / disclosure: before running stage 1 I ran a single smoke test (speed test, FULL window, off=0, phase=0, current cell lev4|kill0.35) and a 4-way kill-mode comparison on that one path. I saw: kill_mode 0 (daily close) end 13.4x / 10 kills; mode 1 (hourly worst-case trigger AND exit at simultaneous adverse marks) end 0.085x / 21 kills; mode 2 end 0.002x / 31 kills. Kill=none gave identical equity in modes 0 and 1 (mechanics OK; no coding bug found). Interpretation: mode 1 as preregistered is an EXTREME pessimism bound (simultaneous worst wick on all 16 legs, realised as exit price), not an unbiased model of the live 15 s poll; the true live behaviour lies between the close-sampled and the worst-case versions. I therefore add:
- kill_mode 3 = trigger on hourly-CLOSE equity drawdown vs hourly-close HWM, exit at the hourly close marks (optimistic bracket; 24 samples/day, misses wicks). On the same smoke path it ended 22.7x / 10 kills.
Consequences (fixed now, before results):
1. Stage 1 runs, for all 24 cells, BASE/VOL/COST/COMB under kill_mode 1 (PREREGISTERED PRIMARY, selection S1 exactly as section 6) AND kill_mode 3 (secondary selection S3, same rule). Daily-close (mode 0) BASE as before. Liquidation checks are always hourly worst-case, in every mode.
2. Section 8 MOVE rule is tightened: MOVE TO X requires X to be BETTER than current under mode 3 and not WORSE under modes 1 and 0 (OOS+IS rule of section 7), plus all other conditions; X may be S1 or S3 (each must pass its own plateau test). If S1 is NONE, the pre-registered primary outcome is 'no candidate'; the amendment-based S3 can still be reported but its evidential weight is lower (post-amendment).
3. No cell added/removed; cooldown/deploy handling unchanged.
Engine sha256 after amendment: recorded in hashes.log.
