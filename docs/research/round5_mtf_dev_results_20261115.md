# Crypto MTF development exploration (not validation)

This is a descriptive replay of a previously explored development interval. It is not a sealed holdout, out-of-sample result, or evidence that the 80% precision target is met.

## Frozen run details

- Interval: `2026-07-17T00:00:00Z` to exclusive `2026-10-09T00:00:00Z` (UTC).
- Symbols: 50; timeframe widths: 1m, 3m, 5m, 10m, 15m, 30m, 60m, 120m, 240m.
- Base setups: bb_squeeze_breakout, orb_funding_session, vwap_band_fade, volume_climax_exhaustion.
- Signal close then next 1m open; at least two fresh timeframe votes must agree; each timeframe has its own structure stop, fixed 2R target, 10/20-bar checkpoint; same-minute barrier ties are stop-first.
- Fee: 0.10% round trip; no slippage, depth, or fillability model.
- Forecast rows (one row per emitted timeframe forecast): 133,046.
- Candle DB SHA-256: `cac23a3d18be66e226bdf8c3dbc0d08f5c6c185d4f18ed2a8687f08d2b6f67b1`.
- Universe JSON SHA-256: `cc27fe897a71368b33d5425dda75ea395705022972abde8a3e18a58ab97dfba8`.
- The universe is the current collection list, not point-in-time membership. Delisted symbols and historical eligibility are not represented.

## Unleveraged outcomes

Precision is target-first count divided by target + stop + timeout; timeout is a non-hit. Mean net R is calculated per emitted forecast after the frozen round-trip fee, with the fixed 2R target. Each 10/20-bar row scores the same forecast cohort at a different deadline.

|TF|Side|Horizon|N|Target|Stop|Timeout|Unscorable|Target-first|Mean net R|
|---:|:---:|---:|---:|---:|---:|---:|---:|---:|---:|
|1m|long|10|22351|3335|9085|9931|0|14.92%|-1.157|
|1m|long|20|22351|4486|10975|6890|0|20.07%|-1.152|
|1m|short|10|22270|3360|9191|9719|0|15.09%|-1.281|
|1m|short|20|22270|4463|11166|6641|0|20.04%|-1.290|
|3m|long|10|16618|3291|7947|5380|0|19.80%|-0.912|
|3m|long|20|16618|4057|9086|3475|0|24.41%|-0.912|
|3m|short|10|16377|3209|8062|5106|0|19.59%|-0.969|
|3m|short|20|16377|3901|9229|3247|0|23.82%|-0.975|
|5m|long|10|10560|2107|4781|3672|0|19.95%|-0.650|
|5m|long|20|10560|2586|5569|2405|0|24.49%|-0.651|
|5m|short|10|10607|2039|5088|3480|0|19.22%|-0.781|
|5m|short|20|10607|2456|5869|2282|0|23.15%|-0.784|
|10m|long|10|6173|1277|2849|2047|0|20.69%|-0.527|
|10m|long|20|6173|1543|3319|1311|0|25.00%|-0.527|
|10m|short|10|6169|1240|2998|1931|0|20.10%|-0.555|
|10m|short|20|6169|1496|3421|1252|0|24.25%|-0.552|
|15m|long|10|4401|895|2087|1419|0|20.34%|-0.537|
|15m|long|20|4401|1095|2441|865|0|24.88%|-0.542|
|15m|short|10|4651|928|2322|1401|0|19.95%|-0.425|
|15m|short|20|4651|1097|2642|912|0|23.59%|-0.430|
|30m|long|10|2873|606|1447|820|0|21.09%|-0.282|
|30m|long|20|2873|759|1668|446|0|26.42%|-0.265|
|30m|short|10|3000|599|1519|882|0|19.97%|-0.344|
|30m|short|20|3000|721|1751|528|0|24.03%|-0.350|
|60m|long|10|1828|389|911|528|0|21.28%|-0.169|
|60m|long|20|1828|509|1050|269|0|27.84%|-0.144|
|60m|short|10|1925|379|994|552|0|19.69%|-0.257|
|60m|short|20|1925|469|1167|289|0|24.36%|-0.270|
|120m|long|10|1072|268|522|282|0|25.00%|-0.030|
|120m|long|20|1072|342|600|130|0|31.90%|-0.006|
|120m|short|10|1084|188|544|352|0|17.34%|-0.175|
|120m|short|20|1084|243|636|205|0|22.42%|-0.183|
|240m|long|10|571|167|262|142|0|29.25%|0.113|
|240m|long|20|571|201|299|71|0|35.20%|0.134|
|240m|short|10|516|80|280|156|0|15.50%|-0.224|
|240m|short|20|516|102|321|93|0|19.77%|-0.216|

## Approximate 4x/5x outcomes at the 20-bar deadline

Liquidation is modeled with the scorer's fixed 0.5% maintenance buffer; it is not an exchange/account-specific liquidation quote. Precision treats liquidation as a non-target outcome. Mean net R is not comparable to unleveraged R because leverage scales P&L.

|TF|Side|Lev|N|Target|Stop|Liquidation|Timeout|Unscorable|Target-first|Mean net R|
|---:|:---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|1m|long|4x|22351|4486|10974|1|6890|0|20.07%|-1.152|
|1m|long|5x|22351|4486|10974|1|6890|0|20.07%|-1.152|
|1m|short|4x|22270|4463|11166|0|6641|0|20.04%|-1.290|
|1m|short|5x|22270|4463|11166|1|6640|0|20.04%|-1.290|
|3m|long|4x|16618|4057|9085|1|3475|0|24.41%|-0.912|
|3m|long|5x|16618|4057|9084|2|3475|0|24.41%|-0.912|
|3m|short|4x|16377|3901|9229|0|3247|0|23.82%|-0.975|
|3m|short|5x|16377|3901|9229|2|3245|0|23.82%|-0.975|
|5m|long|4x|10560|2586|5569|0|2405|0|24.49%|-0.651|
|5m|long|5x|10560|2586|5569|0|2405|0|24.49%|-0.651|
|5m|short|4x|10607|2456|5869|0|2282|0|23.15%|-0.784|
|5m|short|5x|10607|2456|5869|1|2281|0|23.15%|-0.784|
|10m|long|4x|6173|1543|3319|0|1311|0|25.00%|-0.527|
|10m|long|5x|6173|1543|3319|1|1310|0|25.00%|-0.527|
|10m|short|4x|6169|1496|3421|1|1251|0|24.25%|-0.552|
|10m|short|5x|6169|1496|3421|1|1251|0|24.25%|-0.552|
|15m|long|4x|4401|1095|2441|0|865|0|24.88%|-0.542|
|15m|long|5x|4401|1095|2441|0|865|0|24.88%|-0.542|
|15m|short|4x|4651|1097|2642|0|912|0|23.59%|-0.430|
|15m|short|5x|4651|1097|2642|0|912|0|23.59%|-0.430|
|30m|long|4x|2873|759|1668|0|446|0|26.42%|-0.265|
|30m|long|5x|2873|759|1668|0|446|0|26.42%|-0.265|
|30m|short|4x|3000|721|1751|1|527|0|24.03%|-0.351|
|30m|short|5x|3000|721|1751|1|527|0|24.03%|-0.351|
|60m|long|4x|1828|509|1050|0|269|0|27.84%|-0.144|
|60m|long|5x|1828|509|1049|1|269|0|27.84%|-0.144|
|60m|short|4x|1925|469|1166|1|289|0|24.36%|-0.270|
|60m|short|5x|1925|469|1166|1|289|0|24.36%|-0.270|
|120m|long|4x|1072|342|600|0|130|0|31.90%|-0.006|
|120m|long|5x|1072|342|600|0|130|0|31.90%|-0.006|
|120m|short|4x|1084|243|635|1|205|0|22.42%|-0.183|
|120m|short|5x|1084|243|635|1|205|0|22.42%|-0.183|
|240m|long|4x|571|200|297|3|71|0|35.03%|0.130|
|240m|long|5x|571|200|296|5|70|0|35.03%|0.131|
|240m|short|4x|516|102|319|2|93|0|19.77%|-0.215|
|240m|short|5x|516|102|318|6|90|0|19.77%|-0.216|

## Decision

No timeframe/direction cell approaches 80% target-first precision. The best unleveraged 20-bar descriptive cell is 240m long at 35.20% (201/571 targets; mean net R +0.134); it is post-hoc among 36 cells and is not an independently selected winner. Most cells have negative mean net R. This MTF rule therefore does not satisfy the user's high-confidence signal objective and is not suitable for live/manual deployment based on this evidence.

## Missing validation gates

- This development interval was previously explored and is not sealed or out-of-sample.
- Universe is the current collection list, not point-in-time membership; survivorship and listing bias remain.
- Coverage denominator, registered baselines, event/symbol/day clustered confidence bounds, and slippage/depth are not computed.
- Per-timeframe outcomes share consensus events and symbols and are not independent samples.
- Approximate 4x/5x liquidation uses a fixed maintenance buffer, not Binance account-specific liquidation mechanics.
- No coverage denominator was computed, so the registered 10% coverage threshold is untested.
- The registered directional/momentum and fixed-seed random baselines were not replayed; no clustered Wilson bounds or multiplicity adjustment was computed.
- The 80% criterion is plainly missed on descriptive precision, but this is not a complete statistical verdict because the development data were previously viewed and the cohort is not point-in-time.

## Reproduction

Run `python -m chart_predictor.mtf_dev_experiment --db <read-only-db> --universe <symbol-json> --output <report.json> --symbol-limit 50` from the repository root. The command opens SQLite in read-only mode and writes only to the caller-selected output path.
