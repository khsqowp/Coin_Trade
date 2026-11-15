# R005 handoff

## Current state

- Added a single proposed macro-to-micro orderbook-replenishment candidate; it is not a performance-tested strategy.
- Existing L2 pilot raw file passed an independent SHA-256/record/JSON/newline check. The capture is two symbols and approximately one hour; no reconnect occurred naturally.
- Follow-on implementation added offline-only tools at `scripts/research/crypto_l2_compact.py`, `scripts/research/crypto_l2_windows.py`, and `scripts/research/crypto_l2_signal.py`, plus focused synthetic tests. Latest full `chart_predictor/tests`: 242 passed, one environment warning. No live feed was started.
- Two raw-to-compact replays matched SHA-256 `280f5b008cf1668059b7c2ffe600ed598a31699f739f4a53df24b5e7c83a7701`; they processed 208,224 source records, synchronized both books, preserved two connection events, and emitted 208,165 rows. No strategy metrics were calculated.
- Two compact-to-window replays matched SHA-256 `9d98111b41ee5709fec66d8d93c36e6c151f6bd53b9370ed98e09699d5d6e829`. The hour produced 718 UTC 10-second windows; 716 passed data-quality checks, four incomplete tail windows were withheld, and two lacked pre-window depth. Late-event and disconnect counts were zero.
- Each feature window now retains the depth-update quote path (up to 20 samples), one-second trade sub-paths with high/low event times and first/last executable quotes, and the receive-monotonic timestamp when its included features became available. A strict comparator requires all features to arrive before the decision anchor; it rejects equal-time data.
- A completed-T-bar eligibility gate now selects only finalized, quality-ready 10-second windows fully inside that bar and available strictly before the decision receive-time. It separately counts late-arriving, incomplete, bad-quality, out-of-bar, and missing-availability rows. Synthetic tests cover a delayed old-event-time row, exact-decision-time arrival, and invalid bounds.
- A pure offline R005 candidate builder composes that gate with completed T/H input checks, exact UTC bar widths, `H=max(4h,4T)`, BTC macro direction, direction-specific aggression and replenishment thresholds, and earliest-qualifying-window selection. It emits an explicitly unfilled candidate with a pre-entry stop only. Threshold derivation, real-capture replay integration, ATR-vs-R rejection, executable entry/target, costs, and outcome labels remain unimplemented; this is not a backtest result.
- `D_pre` and `D_2s` freshness is frozen at 750 ms (500 ms nominal depth stream interval plus 250 ms jitter allowance). The existing pilot's 716 data-quality-ready count is unchanged; a new synthetic stale-depth-after-gap test rejects older endpoints.
- The aggregate was 13,745,958 bytes uncompressed and 2,091,272 bytes with Zstandard 1.5.7. Linear scaling from one two-symbol hour projects to about 183.20 decimal GB/year for 20 symbols. This is not a measured sustained rate. Temporary replay files were not committed.
- The production recorder/data gate remains closed: the candidate builder is not yet integrated with raw-capture replay or a trailing-30-day threshold calculator; ATR-vs-R rejection and entry/stop/target path replay are absent; quote-path sufficiency for 1,000 USDT execution costs is unverified; and multi-day reconnect recovery plus measured 20-symbol capacity remain untested.
- The five R005 documents were committed and pushed in `0f6fa2870b320da5e257cd643424728ff0a205eb`. The implementation and test changes from this follow-on are not yet committed.
- The raw capture hash is in `manifest.json`. The 20-symbol raw-size projection is explicitly labeled as linear extrapolation and is not a measured rate.
- Zstandard 1.5.7 streaming compression reduced this sample to 44,188,758 bytes (19.14% of the original); the estimated 20-symbol year remains about 3.87 decimal TB at that sample ratio. No compressed file was written.

## Next implementation increment

1. Integrate the pure R005 candidate builder with deterministic capture replay and a prior-only 30-day aggression percentile calculator; prove no future data are used in threshold computation.
2. Implement exact entry/stop/target quote-path replay and top-five depth-walk cost estimates at 1,000 USDT notional; include funding data and mark insufficient depth as unscorable.
3. Extend tests for delayed-event no-lookahead, gaps spanning windows, reconnect invalidation, UTC bucket boundaries, deterministic replay, and output hard caps. Existing pilot remains integrity-only.
4. Test multi-day storage, replay speed, automatic cap behavior, and actual reconnect/resnapshot recovery on bounded local captures before selecting a 20-symbol cohort. The current 183.20 GB/year projection is not production capacity proof.
5. Freeze calibration/sample counts/cost/access decisions and complete every checklist item in `plan.md`; only then register a performance study.

## Separate equity track

KR and US stock/ETF performance sweeps remain blocked by point-in-time universe, inactive/delisted history, corporate actions, data rights, and (for US) a verified licensed dataset. Existing exposed cohorts must not be retuned. The missing user-controlled gate is to confirm an existing qualifying license or authorize the relevant registration/purchase path; no account, contact, purchase, or terms acceptance was performed.
