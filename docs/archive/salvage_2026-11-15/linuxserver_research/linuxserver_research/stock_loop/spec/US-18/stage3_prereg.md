# US-18 Stage 3 prereg (written 2026-11-13 BEFORE unlock_holdout is called)
Candidate set (ONE, frozen from Stage 2 per spec/US-18/stage2_prereg.md): US-18-T100 cell RSI(2)<5, momentum lookback 126 bars, top fraction 0.25 of the PIT top-100 liquid universe, buy close t, exit first close above SMA5 within 5 bars else t+5, USCost default.
(T30 version failed the Stage 2 walk-forward rule and is not a candidate. No other cell is looked at on the holdout.)
Holdout = events whose signal/entry date is >= 2024-11-12 (features computed on the full price history, point-in-time ranks); events straddling the boundary are excluded from both samples.

## Pass criteria (all required; PLAN Stage 3; interpretations fixed here)
1. Net Sharpe >= 1.0 on the holdout slot portfolio with N=10 slots (max concurrent <= 10 as PLAN allows); N=5 also reported.
2. Random-entry baseline >= 95th percentile, >=1000 draws (2000 used), same entry bars, pool = all PIT top-100 names, same exit rule and costs.
3. Net mean > 0 in >=70% of DEV years for the candidate cell.
4. Holdout net mean > 0 at 2x costs.
5. >= 200 holdout trades (events); also report the portfolio-accepted count.
6. Max concurrent positions <= 10 (portfolio N=10).
7. Report worst trade and max drawdown (holdout portfolio).
Unlock: splits.unlock_holdout is called once for this candidate set. Result is final: a failure ends the candidate; there is no re-tuning against the holdout.
If all pass: strict robustness (cost 2x already, T30 breadth with same params, year-by-year, block-clustered t) and results/US_FINAL.md.
