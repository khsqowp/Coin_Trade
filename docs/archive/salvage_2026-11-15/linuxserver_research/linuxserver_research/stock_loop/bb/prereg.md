# BB-01 prereg: intraday Bollinger scalp on "fast risers rank 20-50" (written BEFORE any result)
Status: hypothesis-level screen on a SHORT sample (weeks). Not proof. Survivorship: current constituents / currently listed names only.

## Idea (user, paraphrased from a reel)
Among day's fast risers ranked 20th-50th by intraday % change vs previous close, with active volume: BUY at lower Bollinger band touch, SELL at upper band touch. Scalp, no overnight, long only.

## Data
D1 US: yfinance 5m, last ~60d, regular session, S&P500 (lib us_universe) + hardcoded Nasdaq-100 extras (approx list). Local exchange time (America/New_York).
D2 KR-yf: yfinance 5m last ~60d, top 300 KR names (KOSPI/KOSDAQ via lib kr_universe, ex ETF/pref/SPAC) by mean daily traded value of last 20 daily bars in gulp_pattern cache. Asia/Seoul.
D3 KR-tick: NAS archive /mnt/nas/Ochestration/market-data/tick-archive/2026 kr.jsonl(.gz) (price-only, NO volume, ~40-symbol watchlist, ~2026-10-19..11-11), aggregated to 1m and 5m bars, session 09:00-15:30 KST. (Local trading-tick-archive lives inside Ochestration dir: NOT used.) Because only ~40 names and no volume: rank filter degenerate (ranks 20-50 of 40 = ranks 20-40, laggards), activity filter impossible. D3 is reported as BB-only (no filters) primary + literal rank variant, labelled supplementary.
1m yfinance only covers 7 days: skipped. 1m used only in D3. data/minute collector output: used only if present at run time (it was absent at prereg time) -> not used.

## Operationalisation (fixed, no later changes)
- Rank: at each bar, % change = close/prev-session-last-close - 1, ranked descending among universe symbols with a valid bar. Candidate rank in [20,50].
- Activity filter (ONE choice): cumulative traded value today (sum close*volume) >= 1.5 x mean of cumulative traded value at same bar-of-day over previous up to 20 sessions (min 10). First 10 sessions = warm-up, no trades.
- Bollinger(20, k) of closes, rolling continuous across sessions per symbol (bands as charting platform). k in {2.0, 2.5}.
- Entry signal at bar t (end of bar): low_t <= lower_t, candidate at t, t not among the last 3 bars of session, no open position in symbol.
  BASE: fill at open of t+1 (no lookahead). OPTIMISTIC ("limit at prior band"): low_t <= lower_{t-1}, fill min(open_t, lower_{t-1}).
- Exit (first hit, order within bar: stop > target): stop = entry*(1-s), s in {1.0%,1.5%}, fill min(open, stop) on low touch; target band (upper or middle, grid): BASE signal high_t >= band_t, fill open t+1; OPTIMISTIC high_t >= band_{t-1}, fill max(open_t, band_{t-1}); time stop 12 bars after entry bar -> close; session end -> last bar close.
- One position per symbol, max 5 concurrent (global), tie priority by random seeded key (not rank). Equal weight; return per trade = exit/entry-1 minus cost.
- Grid: k{2.0,2.5} x exit{upper,middle} x stop{1.0,1.5%} = 8 cells per (dataset, bar size, fill variant). Trials counted: D1 8, D2 8, D3 5m 8 + 1m 8 = 32 primary cells (x2 fill variants reported, x filter ablations). All reported.
- PRIMARY pre-declared cell: k=2.0, exit=upper, stop=1.0%, BASE fill. Also "dev-best cell" chosen mechanically by max dev net mean (cost scenario base) with n>=30.

## Costs (lib/costs.py)
KR: KRCost scenario B (sell tax 0.20%, commission 0.015%/side, slip 0.05% liquid/0.10% illiquid per side by 20d traded value); also scenario A (Prime, commission 0), 2x cost. US: USCost default (0.1%/side comm, SEC fee, FX 0.1% RT, slip 0.05%/side), 2x. Always report gross mean, break-even RT cost (=gross mean), avg gross move vs cost.

## Split (strict chronological, per dataset, on tradable sessions after warm-up)
First 70% of sessions = DEV, last 30% = TEST. All design/inspection on DEV only. TEST is run ONCE via a lock file (--phase test refuses to run twice) for all cells; verdict gate uses PRIMARY and dev-best cell on TEST.
Within DEV also report halves (h1/h2) sign consistency. t-stats clustered by session date.

## Baselines / ablations
- Random-entry baseline (>=1000 draws): for each actual trade entry time, random symbol; (B1) from all universe symbols with a valid bar at t, (B2) from the same candidate set (rank+active) at t; entry at next open, same exit rules (stop/target/time/session end), same costs. Report percentile of actual mean among draws.
- Filter ablation: A0 rank20-50+active (main); A1 active only (no rank); A2 no filters (all symbols).

## Verdict rule (fixed)
advance: TEST net mean/trade > 0 for primary and dev-best, clustered |t|>=2 on TEST (sample too short for 3), >=95th pct vs both random baselines, survives 2x cost positive, same sign in DEV h1/h2, n>=100. hurts: net mean significantly < 0 (t<=-2) or filter A0 clearly worse than A1/A2. else noise. Even 'advance' = needs longer minute data; no capital decision.
