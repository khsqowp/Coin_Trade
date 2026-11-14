# US requests / notes for lib (US session, 2026-11-13)
No bugs found; nothing blocking. Suggestions:
1. data.load_index('SPY'/'QQQ') returns raw OHLC plus an 'adj close' column (not adjusted OHLC, no rawclose); I adjust OHLC myself (factor = adj close/close). Consider returning the same schema as load_ohlcv.
2. us_universe() is today's S&P 500 membership (survivorship + index-inclusion lookahead). For US results this is the dominant bias (see results/US_FINAL.md frozen-universe test). A point-in-time constituent list would fix it.
3. eventstudy.make_events with entry ('open',0) uses panel.value20 including bar t for cost only (cost is constant for US); fine, but liquidity ranks for open entries must be lagged by the caller (I do).
4. portfolio.simulate daily series covers only first entry..last exit, so Sharpe is on the active span; fine but keep consistent between markets.
