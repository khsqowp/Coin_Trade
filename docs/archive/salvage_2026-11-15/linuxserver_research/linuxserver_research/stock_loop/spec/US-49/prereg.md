# US-49 - VIX one-day jump (US, Round 9 prereg)

## Signal (fixed)
Mechanism: abrupt fear shock overshoots. Signal: VIX_t/VIX_{t-1}-1 >= +15%. Buy SPY, QQQ, IWM at the close; hold 3 bars.

## Common (Round 9, ETF/VIX/cross-asset family; written 2026-11-13 BEFORE any run of US-42..US-52)
- Round 9 is beyond PLAN's 6-round cap: authorised by the owner ('keep going until meaningful') via the coordinator; recorded in LEDGER.md.
- Origin: single-stock searches exhausted (rounds 1-8, 0 survivorship-robust candidates). ETFs have no stock-survivorship selection problem (liquid, long history). Ideas are first-principles mean-reversion/panic mechanisms; no holdout information used.
- Data: dev only (<= 2024-11-11). ETF pool (31): SPY QQQ IWM DIA, 11 SPDR sectors (XLC/XLRE start later), EFA EEM EWJ EWZ FXI, TLT IEF HYG LQD, GLD SLV USO DBC, VNQ, XBI SMH; adjusted prices via lib loaders (17 missing ETFs downloaded once, rate-limited). VIX = FinanceDataReader 'VIX' (Yahoo ^VIX close), saved in results/us42_raw/; VIX3M/VXN not available (404) and skipped.
- Thresholds below are FIXED a priori (round numbers from the mechanism, no grid in Stage 1). Each hypothesis = ONE trial (pooled over its instruments); per-instrument and per-year tables are descriptive only and not used for selection.
- Entry at the close of the signal bar; costs USCost RT 0.403% (2x and 3x also reported). Verdict (Stage 1): net mean>0, t clustered by ISO CALENDAR WEEK of entry >= 3 (this is the block-t; it dedupes clustered crash-day signals), and mean>0 in both halves (split at the midpoint of the event date span). Additional reports: lib date-clustered t, break-even round-trip cost (= gross mean), 2x/3x mean, per-year means and share of years positive, number of events, number of distinct weeks with events (episodes) and the effective independent sample size n_eff = number of distinct weeks, slot-portfolio Sharpe (N=5 for pooled ETF, N=3 for VIX instruments).
- Stage 2 only for Stage 1 survivors: <=3 params x 3 values, plateau, walk-forward, BH q<0.10 over the cumulative list (196 before this round, 207 after). Holdout stays locked unless Stage 1 + Stage 2 are cleared; every holdout look is logged (3 so far, all US-18-T100).
