# Slice 2 - SKIPPED specs (no plugin written)

| spec id | reason |
|---|---|
| commodity-futures-roll-momentum-double-sort | Needs commodity futures nearby/second-nearby contract data (roll return) and a cross-sectional monthly universe; not in crypto OHLCV cache. |
| qqq-btc-donchian-rotation | Needs QQQ equity data and the equity-session calendar (rotation at QQQ close); not available. |
| c4-estrategia-larry-connors-josemetal | Entry/exit rules reference undefined composite variables (`all_LONG_conditions`, `exit_LONG_conditions`); conditions are not in the archived spec, so no faithful implementation is possible without inventing them. |
| c4-grid-tool | Entry rules are undefined variables (`entry_long_1/2`, `inst_pos`, ...); grid/DCA with partial closes, scalping mode and pivot/fractal repaint risk, not expressible in the engine. |
| c4-js-techtrading-supertrend-strategy-basic-version | `buy_cond`/`sell_cond`/`longOK`/`longStop` are undefined; 'Pullback' vs 'Simple' variants are not described in the spec. |
| c4-pt-premarket-breakout-strategy | Equity pre-market session (09:00-09:30) / entry session (09:45-15:45) rules and undefined `L_entry1`, `L_exit1`; also uses daily ATR via security. Not definable from archived spec and crypto trades 24h. |
| c4-th-volatility-breakout | Archived entry is just `true` (the breakout level/range formula is not in the spec; only k=0.5 input), so the rule cannot be reproduced without inventing it. |
| c4-ultimate-ichimoku-cloud-strategy | Only long entry toggles are listed; short conditions, exit conditions (`long_exit`/`short_exit`) and the SL/TP switch (`i_use_SLTP`) values are undefined. |
| c4-crunchster-s-turtle-and-trend-system | Entry depends on undefined `nemadiff`/`signal` series and `openN` (volatility-target position-sizing machinery); not recoverable from the archived text. |
