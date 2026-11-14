# US-ADDENDUM-data (dated 2026-11-13, written BEFORE any US run; US session)

The US-01..US-12 preregs say "KIS daily data, top-30 liquid names (60-day median dollar volume)". The harness data differ.
This addendum states the substitutions. Nothing else in the preregs changes (signals, exits, defaults, thresholds stay as written).

## Data
- Source: harness cache (lib/data.py): 503 CURRENT S&P 500 names, split/dividend-adjusted OHLC (adj factor = AdjClose/Close) from
  a public source (FinanceDataReader), ~2009/2010 .. 2024-11-11 for dev. Holdout (>= 2024-11-12) stays locked (lib guard); unlock_holdout is not called in Stage 1-2.
- SURVIVORSHIP BIAS: the universe is today's S&P 500 members (winners that stayed/entered the index); delisted/removed names are absent.
  This inflates long-only returns, especially for dip-buying and momentum signals. Every positive result is discounted for it; it cannot be fixed with this data.
- ETFs: SPY and QQQ from lib idx cache (open/high/low/close raw + 'adj close'; I adjust OHLC by adj close/close myself). IWM + the 11 SPDR sector ETFs
  (XLB XLC XLE XLF XLI XLK XLP XLRE XLU XLV XLY) are not in the cache: downloaded once via lib.data.load_ohlcv (public, 0.4 s rate limit), cached under lib/cache/us/.
  XLC (since 2018-06) and XLRE (since 2015-10) have short history; US-10 uses whichever ETFs have data on each day (bottom-2 among available).

## Universe definition
- DEFAULT: point-in-time top 30 by lib `value20` (20-day mean traded value = rawclose*volume, known at bar t incl. t), ranked each day over the 503 names.
  (Deviation from prereg: 20-day mean instead of 60-day median, because that is what lib provides.) For entries at the open of day t (US-01) the rank uses value20 lagged one bar.
- BREADTH VARIANT (pre-declared now): top 100 by the same measure. Reported side by side; each variant is a SEPARATE trial in the trial count.
- Applies to stock-based hypotheses (01,02,04,05,06,07,09-stocks,11,12, and 03-universe). ETF hypotheses (03 SPY/QQQ, 08, 09-SPY, 10) have no breadth variant.

## Interpretations fixed before running
- Costs: lib.costs.USCost() default (round trip = 2*0.10% + 0.00278% + 0.10% FX + 2*0.05% = 0.40278%), plus mult=2 sensitivity. Same cost for ETFs.
  Break-even round-trip cost = gross mean per trade (lib convention) is reported for every strategy.
- Trade = one (signal, symbol) event; the verdict statistic uses ALL events (overlapping allowed) exactly like the KR Stage 1 (lib.eventstudy.summarize,
  t clustered by entry date, halves split at the midpoint of the dev calendar). PLAN Stage 1 pass rule is applied unchanged: net mean > 0, t >= 3, both halves > 0.
- ADDITIONAL (stricter, reporting only): block-clustered t (cluster = 5-bar block of the entry date) because holds of 3-5 days overlap; any "advance" with block-t < 2 is flagged as fragile.
- Portfolio view: lib.portfolio.simulate with N=5 slots (US-10: N=2), first-come ordering, as in PLAN. Reported: Sharpe, max drawdown, worst trade, max concurrent.
- Variable exits (US-04, US-05, US-11): exit at the first bar k in 1..H whose condition holds (evaluated at that bar's close, executed at that close), else at H; ties/NaN bars: event dropped if the exit price is missing.
- US-01: mask evaluated on day t with entry=open t, exit=close t; "prior day" quantities (close_{t-1}, SMA200_{t-1}, volume_{t-1}/avg20 vol_{t-1}) are lagged one bar.
- US-04: IBS = (close-low)/(high-low) (bars with high==low excluded). US-05: lib.features.rsi (Wilder, n=2). US-07: ATR(14) = 14-bar simple mean of true range, lagged one bar.
- US-06: day-by-day rank of 3-day return (close_t/close_{t-3}-1) inside the eligible universe; selected = the k lowest with k = max(3, floor(0.10*n_eligible)) (30 -> 3 names, 100 -> 10 names), only those with close_t > SMA200.
- US-08: buy close of the second-to-last trading day of each month (by trading calendar), sell close 4 trading bars later (= 3rd trading day of next month); SPY and QQQ separate trials.
- US-09: Friday = weekday 4 in the trading calendar; exit = close of the next trading bar; SPY trial (ret <= -1.0%) and universe-stocks trials (stock Friday return <= -2.5%, unconditional on SPY, top30 and top100).
- US-10: relative 5-day return = ETF 5d return - SPY 5d return; bottom 2 of the available sector ETFs on each day, subject to own close > SMA200; hold 5 bars.
- US-11: "new 20d low yesterday" = low_{t-1} < min(low_{t-21..t-2}); protective exit = first close_{t+k} < low_{t-1} (k=1..5), else close t+5.
- US-12: SPY ret_t <= -0.75%, stock ret_t >= +1.0%, stock close_t > SMA50, entry close t, exit close t+3.
- US-03 variants (all are separate trials): {SPY, QQQ, universe-30, universe-100} x {unconditional, close<SMA5}; buy close t, sell open t+1.
- Trial counting for Stage 1: every row of the ledger (strategy x variant) is one trial; BH q is computed over the cumulative trial list.

## Further interpretations (appended 2026-11-13, still before any run)
- US-02 volume ratio: volume_t / mean(volume_{t-20..t-1}) >= 3 (average excludes the event day itself).
- US-01 "its 20d average" = mean of volume over the 20 bars ending t-1 (includes t-1).
- Events whose hold window runs past the last dev bar are dropped (lib NaN convention); events with a missing exit price are dropped.
- Dev calendar = SPY idx calendar (2009-12-31 .. 2024-11-11); US-08 skips partial months (< 15 trading bars in calendar).
- Output files: results/US-xx/summary.json (all variants of that hypothesis), trades_<variant>.parquet (all events, or a seeded 50k sample if larger), results/US_stage1.json (all).
