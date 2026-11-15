# R005 handoff

## Current state

- Added a single proposed macro-to-micro orderbook-replenishment candidate; it is not a performance-tested strategy.
- Existing L2 pilot raw file passed an independent SHA-256/record/JSON/newline check. The capture is two symbols and approximately one hour; no reconnect occurred naturally.
- Follow-on implementation added offline-only tools at `scripts/research/crypto_l2_compact.py` and `scripts/research/crypto_l2_windows.py`, plus focused synthetic tests. Full `chart_predictor/tests`: 231 passed, one environment warning. No live feed was started.
- Two raw-to-compact replays matched SHA-256 `1d12080bc7e8a8f4814334541d7a6865716d2362e38862ddfca7a3c08e96687a`; they processed 208,224 source records, synchronized both books, preserved two connection events, and emitted 208,165 rows. No strategy metrics were calculated.
- Two compact-to-window replays matched SHA-256 `262d90141cd089a800f691389faedc42d68da4d3cb19c2693390c291cd2758d4`. The hour produced 718 UTC 10-second windows; 716 passed data-quality checks, four incomplete tail windows were withheld, and two lacked pre-window depth. Late-event and disconnect counts were zero.
- The aggregated file was 1,054,384 bytes uncompressed and 186,557 bytes with Zstandard 1.5.7. Linear scaling from a single two-symbol hour projects to about 16.34 decimal GB/year for 20 symbols; this is not a measured sustained rate. Temporary replay files were not committed.
- The production recorder/data gate remains closed: feature availability versus each T-bar decision, full executable entry/exit paths and cost snapshots, multi-day reconnect recovery, and a measured 20-symbol capacity test remain unverified.
- The five R005 documents were committed and pushed in `0f6fa2870b320da5e257cd643424728ff0a205eb`. The implementation and test changes from this follow-on are not yet committed.
- The raw capture hash is in `manifest.json`. The 20-symbol raw-size projection is explicitly labeled as linear extrapolation and is not a measured rate.
- Zstandard 1.5.7 streaming compression reduced this sample to 44,188,758 bytes (19.14% of the original); the estimated 20-symbol year remains about 3.87 decimal TB at that sample ratio. No compressed file was written.

## Next implementation increment

1. Add explicit per-event receive-time eligibility checks against each completed T/H decision anchor. A window with post-anchor feature receipt must be unscorable at that anchor, even if its exchange event timestamp lies inside the window.
2. Preserve minute-level executable bid/ask price paths and depth-walk snapshots at candidate entry/exit, funding timestamps, book-validity intervals, and reconnect boundaries. Do not infer fill or cost from midprice alone.
3. Extend tests to check delayed-event no-lookahead, sequence gaps spanning a window, disconnect/reconnect invalidation, symbol UTC bucket boundaries, deterministic replay, and output hard caps. Existing pilot remains integrity-only.
4. Test multi-day storage, replay speed, automatic cap behavior, and actual reconnect/resnapshot recovery on a bounded local capture before selecting a 20-symbol cohort. The current 16.34 GB/year projection is not production capacity proof.
5. Freeze calibration/sample counts/cost/access decisions and complete every checklist item in `plan.md`; only then register a performance study.

## Separate equity track

KR and US stock/ETF performance sweeps remain blocked by point-in-time universe, inactive/delisted history, corporate actions, data rights, and (for US) a verified licensed dataset. Existing exposed cohorts must not be retuned. The missing user-controlled gate is to confirm an existing qualifying license or authorize the relevant registration/purchase path; no account, contact, purchase, or terms acceptance was performed.
