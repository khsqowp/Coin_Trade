# US-18 Stage 2 prereg (written 2026-11-13 after Round 2 Stage 1 result, BEFORE any grid cell is run)
Stage 1 (defaults): T30 n=3168 net +0.324% t=3.07 (halves +0.39/+0.26); T100 n=10135 +0.290% t=3.66 (halves +0.43/+0.16). 2x-cost dev mean is NEGATIVE (-0.08% / -0.11%): a known weakness.
Survivorship caveat: strong-6-month-return names in a CURRENT S&P 500 list are biased toward names that kept rising; stated and discounted.

## Grid (3 params x 3 values = 27 cells per universe; both universes = 54 new trials, ALL counted in the cumulative BH list)
- RSI(2) threshold: 5 / 10 (default) / 15
- Momentum lookback: 63 / 126 (default) / 252 bars
- Momentum top fraction of eligible universe: 0.25 / 0.333 (default) / 0.50
Exit unchanged (first close above SMA5, else 5 bars). Everything else unchanged.

## Pass rules for Stage 2 (fixed now)
1. Plateau: >=70% of the 27 cells have net mean>0 AND clustered t>=2; and all 6 one-step axis-neighbours of the default cell have net mean>0.
2. Walk-forward (expanding window, test years 2014..2024): each test year choose the cell with the best mean net return on events from earlier years (>=100 events), take that cell's year-Y events; pooled OOS net mean>0 and t>=2.
3. Default-cell BH q<0.10 over the cumulative trial list (45 Stage 1 trials so far + 54 grid cells = 99).
4. Random-entry baseline for the default cell, 1000 draws, same entry bars; two pools: (a) all eligible names, (b) names in the same momentum top fraction without the RSI condition (isolates the RSI trigger). Need >=95th pct for pool (a); pool (b) is reported.
5. Positive net mean in >=70% of dev years for the default cell.
Candidate for Stage 3 = the cell with the highest mean over {cell + its axis-neighbours} net means (ties -> default), only if rules 1-3 pass for that universe. Portfolio stats at N=5 and N=10 (N<=10 allowed) reported for the candidate.
Pre-gate before spending the holdout: the candidate dev net mean at 2x cost must be > 0, else the holdout is NOT unlocked (a known failing criterion should not burn the single look); documented in US_STATE.md.
