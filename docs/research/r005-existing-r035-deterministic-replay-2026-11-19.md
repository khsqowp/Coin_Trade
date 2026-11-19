# R005 existing R035 capture replay audit — 2026-11-19

## Scope

Read-only replay of the already captured 20-symbol R035 feasibility segment. No exchange connection, new capture, strategy signal, forward label, M2 outcome, or performance metric was generated. Outputs were written only to a fresh `/private/tmp` directory.

## Input

- Capture: `chart_predictor/data/crypto_l2_pilots/20symbol-feasibility-20261117/20261117T060240Z-1424c652/capture.jsonl`
- Capture SHA-256: `7e4c8171ddea6e95bf1a7a559ef59e864d9d0d69bb24c4562e89fbd479be588e`
- 9,760 records; 10,569,425 bytes. The original R035 report records 125.282 seconds of capture, not 60 minutes.
- Replay code: `scripts/research/crypto_l2_compact.py`, then `scripts/research/crypto_l2_windows.py` (10-second windows).

## Replay result

The two independent executions over the same immutable capture produced byte-identical compact JSONL and byte-identical window JSONL (`cmp` passed for both pairs).

| Stage | Rows | Bytes | SHA-256 | Key checks |
|---|---:|---:|---|---|
| Compact | 9,567 | 6,257,784 | `e6600677be70782478c7a4442b2ca99c3d7e808f3df0b445eb173aa633be7f43` | 20 synchronized snapshots; 0 invalidations; 2 feed events preserved; 0 possible trade-ID gaps; 0 duplicate/out-of-order trade IDs dropped |
| 10-second windows | 220 | 3,729,704 | `9dac9ee6676a5ddef3a9d9940e0acf1ce18406e428bebd2b18813d0f49294553` | `quality_pass=true`; 0 late input rows; 40 unfinalized windows withheld; 0 late-invalidated windows; 0 unknown-time feed events; 2 global feed events; 0 disconnect events |

## Decision and limits

**Deterministic replay: PASS for this existing 125-second R035 segment.** This confirms repeatable compact/window transformation for that file only. It does not prove exchange event completeness, natural reconnect recovery, long-duration resource behavior, 60-minute collection, cost calibration, signal efficacy, or the frozen M2 target-first gate. The 40 incomplete tail windows were correctly withheld rather than finalized.

Do not count the 2 global feed events as disconnects: the window manifest reports 0 disconnect events. Do not treat `quality_pass=true` as a strategy result. No new prospective collection was started; storage/retention approval and a reviewed 60-minute capture protocol remain prerequisites for that next infrastructure gate.
