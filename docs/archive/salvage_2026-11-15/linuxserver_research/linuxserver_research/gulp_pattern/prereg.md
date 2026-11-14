# PREREG: "gulp" shakeout-rebound pattern, KR + US daily (research only)
Written before any signal/backtest was computed. No parameter changes after this file is timestamped. Source idea: Instagram reel by 차우주리서치 (rules paraphrased by owner).
Research only: no orders, no live keys, no running service touched. Public data only.

## Seen before writing
Only data inventory (file counts, schema, date ranges, universe status counts). No price statistic of this pattern. Owner's earlier research (kr_daily_v1/v2, us_daily_v2/v3) exists; its conclusions (no edge in generic KR/US daily rules) are prior knowledge, disclosed.

## Data (executed on linuxserver; no existing stock daily history there outside bot state volumes, which are not read)
Public data only, downloaded at low rate (single process, sleep between calls) into /home/noroot/research/gulp_pattern/cache, via FinanceDataReader (KR: Naver daily, adjusted prices; US: Yahoo, columns Open High Low Close Volume Adj Close). No keys.
KR: universe = FDR StockListing("KRX") rows with Market in {KOSPI, KOSDAQ} (current listings, ~2,720). Fetch 2010-01-01..latest in two windows (Naver caps one call at 3000 rows). KR traded value = close*volume (no Amount history). 
US: universe = current S&P 500 (FDR StockListing "S&P500") UNION current Nasdaq-100 (Wikipedia table via pandas.read_html). Adjusted OHLC = OHLC * (Adj Close / Close). Liquidity uses raw Close*Volume.
SURVIVORSHIP WARNING (both markets, severe): the universe is TODAY's constituents/listings. Delisted, bankrupt, merged-out names are absent (KR delisted present: 0; US: 0 historical members). Dip-buy of "shakeouts" is exactly where losers that never recovered are missing, so every result is optimistic. Quantified in report as: n delisted present = 0, and listing-year distribution of universe (share of names listed before 2015). A larger survivorship-reduced KR set (incl. 1,072 delisted) exists on another machine and is NOT used here by instruction.
Index benchmarks: KR KOSPI (KS11), KOSDAQ (KQ11) via FDR; US SPY, QQQ (adjusted close) via FDR.

## Universe filters
KR: Market in {KOSPI, KOSDAQ}; code ends with '0' (common stock, excludes preferred); Name not matching 스팩|기업인수목적 (SPAC); Dept/ETF rows absent from this listing; administrative-issue flag NOT available (stated limit). Liquidity: mean of close*volume (KRW) over the 20 bars t-20..t-1 (bars before drop bar) >= 1.0e9 KRW.
US: index constituents only (ETFs absent); ADR flag not available (stated limit). Liquidity: mean of raw close*volume over bars t-20..t-1 >= 2.0e7 USD.
Bar validity (both): volume>0 on all bars t-N..t+1; no gap between consecutive rows > 7 calendar days within t-N..t+1; no |daily return| > 0.5 within the window (data artifact).

## Signal definition (drop bar t, trigger bar t+1), all on adjusted prices
Consolidation = bars t-N..t-1. Cond C: (max high - min low)/mean close <= R.
Drop: ret_t = close_t/close_{t-1}-1 <= -D; volume_t >= M * mean volume of the N bars t-N..t-1; close_t < min low of consolidation bars.
Untradeable/artifact drop exclusion:
 KR: daily limit L = 0.15 before 2015-06-15, 0.30 from 2015-06-15. Exclude if ret_t <= -(L-0.01) (at lower limit or artifact).
 US: exclude if ret_t <= -0.25 or |open_t/close_{t-1}-1| > 0.25 (halt/gap/artifact). No price limit.
Trigger t+1: close_{t+1} > open_{t+1} AND close_{t+1} > close_t. KR extra: skip if ret_{t+1} >= L-0.01 (limit-up lock, cannot buy).
Entry: E1 = close_{t+1}. E2 = open_{t+2} (bar t+2 must exist). Entry bar e = t+1 (E1) or t+2 (E2).
One position per stock at a time: a signal is ignored if its entry bar is <= the exit bar of the stock's previous accepted trade (same rule for the no-confirmation variants).

## Exits (bar counts from entry bar e)
X1_H, H in {3,5,10}: exit at close of bar e+H.
X2: target T = close_{t-1} (pre-drop close). If entry price >= T, no target (stop/time only). Stop level S = low_t (drop bar low), close-based: exit at the close of the first bar after entry (E1: from t+2; E2: from t+2 including the entry bar itself) whose close < S. Target: first bar whose high >= T, exit price = T. If both occur in the same bar: stop first (exit at that bar close). Max hold: exit at close of bar e+10.
If data for the stock ends before the exit bar: trades whose exit bar is beyond the last available bar are dropped as incomplete (no delisted names exist in this data).

## Grid (fixed, reported in full)
N {15,20} x R {0.10,0.15} x D {0.05,0.08} x M {2,3} x entry {E1,E2} x exit {X1_3,X1_5,X1_10,X2} = 128 combos per market, 256 trials total. Everything else (2x cost, ablations, controls) is report-only and not a selectable/counted trial.
Note: US uses the same numbers as KR (specified by owner), even though daily vol differs.

## Costs (round trip, applied once per trade on net return, as return subtraction)
KR: 2 x 0.015% commission + 0.18% sell tax + 2 x 0.10% slippage = 0.41%. 2x sensitivity = 0.82%.
US: commission 0, slippage 2 x 0.05% = 0.10% (SEC/TAF fees negligible, ignored). 2x sensitivity = 0.20%.

## Event-level view
Per combo: n trades, mean gross forward return at +1,+3,+5,+10 bars after entry (E1: close_{e+k}/entry-1; E2 same from open entry), and net-of-cost mean at +5 and +10 (cost subtracted). Forward windows only when data exist.

## Portfolio view (per combo, cost base and 2x)
Equal weight 1/10 of NAV per position, max 10 concurrent. Trades sorted by entry date; ties by larger volume ratio (volume_t / mean prior volume). Signal ignored if 10 slots are occupied; a slot is free only if the earlier position's exit date < new entry date. Daily portfolio return = (1/10) * sum over open positions of that position's daily return (marked at close; E1 entry day return 0; E2 entry-day return = close/open-1; full round-trip cost subtracted on exit day); idle cash earns 0 (constant 1/10 weight daily-rebalanced approximation, stated). Metrics: CAGR (over period calendar span), Sharpe (daily mean/std*sqrt(252), rf=0), max drawdown, trade count (accepted), win rate, mean/median trade return, worst trade, avg hold in bars, per-year table (return, trades) for ALL.

## Validation
Split by ENTRY date: IS 2010-03-01..2019-12-31 (both markets, burn-in for first windows), OOS 2020-01-01..last. Both markets: IS-selected combo = argmax IS net Sharpe (base cost) among combos with >= 30 IS trades; report its OOS. PBO-style: Spearman rank correlation of IS vs OOS net Sharpe over all combos, and P(IS-top-quartile combo falls below OOS median). Also rolling by year table of mean net trade return per combo-set (median over combos).
(a) Random-entry baseline: for each combo, each real trade is replaced by an entry at a random bar of the SAME stock in the SAME calendar year as the real signal, among bars passing the liquidity and bar-validity filters with enough forward data, same entry type, same exit rule (X2: same relative target/stop offsets as the real trade). 1000 draws; statistic = mean net trade return of the set; report percentile of real mean among draws and one-sided p.
(b) Buy&hold: KOSPI, KOSDAQ (KR); SPY, QQQ (US): CAGR, Sharpe, maxDD over ALL, IS, OOS.
(c) Confirmation ablation: same drop bars (all conditions except trigger), unconditional entry (E1 = close_{t+1}, E2 = open_{t+2}) with the same exits, for all 128 combos; report mean net trade return confirmed vs unconfirmed vs the "failed-trigger" subset, with cluster-bootstrap CI of (confirmed - failed).
(d) Volume ablation (report-only): M = none (0) for N x R x D x entry x exit (64 combos/market) vs M in {2,3}.
(e) Bootstrap: cluster bootstrap (cluster = calendar month of entry date), 5000 resamples, on mean net trade return per combo (ALL, IS, OOS): 95% percentile CI, two-sided p = 2*min(P(boot<=0),P(boot>=0)) floor 1/5000. Multiple testing: Bonferroni (x128 per market; x256 combined) and Benjamini-Hochberg q over the 128 ALL-period p-values per market.

## Verdict rule (fixed now)
helps: OOS net mean trade return > 0 with BH q < 0.10 for the IS-selected combo AND real mean above 95th percentile of random draws in both IS and OOS (index buy&hold comparison and portfolio metrics are reported, not part of the rule).
hurts: median over the 128 combos of net mean trade return < 0 AND IS-selected combo OOS net mean < 0.
noise: otherwise.
Combined verdict: helps only if both markets helps; hurts if either hurts and none helps; otherwise noise.

## Limits (stated now)
Daily bars cannot see the intrabar order-book / "light order book" claim: untestable. Close-based entries assume fill at close (closing auction) at slippage cost. Portfolio approximation as above. 20-bar liquidity and closes use adjusted data of vendor; KR administrative-issue and US ADR flags unavailable. Multi-testing: 256 trials; single pass, no retuning.
