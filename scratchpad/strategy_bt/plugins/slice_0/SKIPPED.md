# Slice 0 – SKIPPED specs (no plugin written)

Reason categories: UNDEFINED = the archived spec refers to Pine variables/conditions that are not defined anywhere in the archive (the Pine source itself is not archived), so no faithful implementation is possible without inventing the strategy. DATA = needs data we do not have. HARNESS = rule needs state the harness cannot express.

| spec_id | reason |
|---|---|
| crypto-pure-momentum-bottom2-top2 | DATA/HARNESS: cross-sectional ranking of a coin universe every hour (long 2 lowest / short 2 highest 24-lagged 1h returns); harness evaluates one symbol per plugin call, with no access to the other symbols, and the paper's eligible-coin universe is not defined. Spec also flags the sign convention as unverified. |
| upbit-30m-spike-chase-10pct | DATA: Upbit KRW markets, 5-minute bars (not cached; smallest cached is 15m, where a 30-minute lookback is 2 bars) and a 24h KRW trading-value eligibility filter (>= KRW 100m) that cannot be built from Binance USDT bars. |
| c4-bb-keltner-squeeze-strategy | UNDEFINED: entry is `midc[1]==0 and midc==1/2`; `midc` and the squeeze/"all conditions" are not defined in the archive. |
| c4-double-supertrend | UNDEFINED: `condLong`, `condShort`, `diffFromTop/Bottom`, `longTakeProfit`, `supertrend1/2`, `rangeMiddleValue` not defined; exit depends on an exitType switch with ATR/range take-profit formulas not given. |
| c4-fair-value-strategy-ultimate | UNDEFINED: `overbought_signal`/`oversold_signal` not defined; also flagged as higher-timeframe/repaint dependent (request.security) needing causal review of the missing source. |
| c4-spx-fair-value-strategy-ultimate | same as above (UNDEFINED signals; HTF/repaint). |
| c4-i11l-reversal-trading-ideas-by-larry-connors | UNDEFINED: `isLowest`, `isClose` (lookbacks) not defined; averaging-in rule needs `strategy.opentrades` pyramiding state. |
| c4-ms-hypersupertrend | UNDEFINED: `extremebullish`, `emacolor`, `entry_price`, `take_profit_long`, RSI exit conditions not defined. |
| c4-supertrend-with-multiple-filter-strategy | UNDEFINED: `longCondition`/`shortCondition`, stop/take-profit price formulas, trailing parameters not defined; spec warns about higher-timeframe lookahead and pivot confirmation. |
| c4-trend-following-with-donchian-channels-and-macd | UNDEFINED: `h1`/`l1`, `entrycondition2/3`, `sellcondition1/2/3`, `stoploss` not defined. |
| c4-villa-dinamic-pivot-supertrend-strategy | UNDEFINED: `ema_cond_*`, `dema_cond_*`, `dema_ang_cond_*`, `st_entry_cond*`, `din_tp`, `sl_*_n/tp_*_n` not defined; pivot (right-side confirmed) conditions. |
| ft_strategy001 | HARNESS: published rule uses a time-since-entry ROI table (5%/4%/3%/1% at 0/20/30/60 min) and `exit_profit_only=True` (exit signal acts only when in profit), both position-state dependent and not expressible by stateless per-bar signals + fixed tp/stop; claimed timeframe 5m is not cached (smallest is 15m). Implementing without them would be a different strategy. |
| jesse_ifr2 | DATA: requires TA-Lib `HT_TRENDMODE` (Hilbert transform trend mode), not installed in the venv and warm-up dependent (spec itself flags it as unstable); a from-memory re-implementation would not be faithful. Ichimoku params (20/30/120/60) are given but the cloud-displacement convention is not. |
| pk_ema_price_800 | UNDEFINED: exit threshold `threshold_percentage` value is "defined in file" but not recorded in the archive; the commented-out ROI table is also not archived. |
