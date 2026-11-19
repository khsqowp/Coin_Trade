# R005 pilot replay audit — 2026-11-19

## Result

The one-hour BTCUSDT/ETHUSDT L2 integrity pilot is present in the current checkout and was replayed through the current compact reducer and 10-second window aggregator. This corrects the older handoff statement that the raw capture was absent from the accessible checkout. The replay is data-pipeline evidence only: no R005 candidate was emitted or scored, and no accuracy, target-first rate, expectancy, PnL, or profitability metric was calculated.

## Source identity and provenance

- Input: `chart_predictor/data/crypto_l2_pilots/20261115T144322Z-a527cf09/capture.jsonl`.
- Capture manifest `run_id`: `20261115T144322Z-a527cf09`; its complete segment entry names `capture.jsonl`, records 230,845,049 bytes and 208,224 rows, and gives SHA-256 `ee337e99a4f3060ec7f56889f35eb4ed213839356a7efc1533ff7a97904d057e`.
- Recomputed input SHA-256 matches the manifest. The current reducer parsed all 208,224 newline-terminated JSON records and matched the manifest byte and row counts.
- The source capture has no `receive_clock_domain` field in any of its 208,224 records. The current compact reducer previously filled this field from the containing directory name without checking the capture manifest. That was not adequate provenance.
- The reducer now derives a legacy domain only from a sibling complete manifest whose segment path, SHA-256, byte count, and record count match the input. Explicit per-record domains that conflict with that manifest fail closed. A legacy file without a matching manifest is rejected. The manifest is not signed; this check establishes internal consistency, not cryptographic authenticity.

## Deterministic replay

- Compact reducer: 208,224 source records → 208,165 rows; two synchronized snapshots; zero invalidations; two connection/feed events; zero duplicate or out-of-order aggregate-trade IDs dropped; zero possible trade-ID gaps. Output SHA-256: `e35512f23f31111672e40514320f45e5046bbfd3d4ab32d1c174a35ae71d3837`.
- Repeating the compact replay produced byte-identical JSONL output (`cmp` exit 0).
- Window aggregator: 208,165 compact rows → 718 finalized ten-second windows, 359 per symbol; 716 windows marked data-quality-ready, two not ready; four unfinished tail windows withheld; zero late rows and zero disconnects. Aggregate `quality_pass` is true under its feed-level rule. Output SHA-256: `473eedf7efc2ecf72e249de72f102418dbd28b0fa5af9c19c04f6678ae0be470`.
- Repeating the window aggregation produced byte-identical JSONL output (`cmp` exit 0).
- The `quality_pass` flag is not a strategy/data-adequacy pass. The two blocked windows remain excluded, and this one-hour run does not establish multi-day continuity or reliable live capture.

## Validation

- `chart_predictor/tests/test_crypto_l2_compact.py`: 37 passed after adding manifest-bound clock-domain checks and fail-closed regression tests.
- Focused L2 suite (`test_crypto_l2_compact.py`, `test_crypto_l2_execution.py`, `test_l2_book.py`, `test_crypto_l2_pilot.py`, `test_crypto_h3_l2_pilot.py`): 107 passed.
- `git diff --check`: passed.

## Decision and next gate

R005 remains `candidate_spec_pending_data_pipeline`; this replay does not authorize a performance test. The pilot has only two symbols and about one hour, versus the candidate's 20-symbol cohort, 30-day prior-feature history, completed 4-hour-or-higher BTC context, calibration/validation partitions, and at least 200 non-overlapping outcomes per evaluated timeframe. No valid target-first sample can be claimed from this replay.

The next admissible work is to finish and test the compact prospective recorder and integrate raw-capture → finalized bars/windows → candidate construction → executable quote replay without emitting market-performance aggregates. Before any prospective run, freeze and test multi-day reconnect/recovery behavior, storage caps, clock-domain provenance, funding coverage, and 20-symbol capacity. Do not launch the old raw JSONL recorder for a long run: its previous 20-symbol annual storage estimate was a linear extrapolation and extremely large, not a measured capacity guarantee. No Oracle build, server transfer, restart, or live capture was performed in this audit.

## Related microstructure candidate screen

The published `turn-of-the-candle` study reports elevated average one-minute BTC returns at 15-minute candle boundaries, not an 80% target-first directional signal over 10–20 bars. It is useful as a fixed timing baseline only if its precise rule and cost assumptions are preregistered. Its reported one-minute horizon does not qualify it as the current R005 candidate; the paper's 2021–August 2022 evaluation dates also overlap the project's documented candle-data span, so they cannot be assumed to be an untouched holdout. Exact timestamp-level overlap has not been checked. Trade-arrival self-excitation/Hawkes models have a distinct event-time mechanism in the literature, but the proposed rule still lacks a frozen event definition and executable historical quotes. Neither candidate received a performance test in this audit.

Primary references: [Shanaev, Vasenin & Stepanov (2023), *Turn-of-the-candle effect in bitcoin returns*](https://doi.org/10.1016/j.heliyon.2023.e14236); [Bacry & Muzy (2013), *Hawkes model for price and trades high-frequency dynamics*](https://arxiv.org/abs/1301.1135).
