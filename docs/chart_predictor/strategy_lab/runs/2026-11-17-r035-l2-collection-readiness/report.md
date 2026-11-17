# R035 — 20-symbol public L2 collection readiness

## Result

**Collection feasibility: pass for a short 20-symbol sample. Strategy efficacy: not tested.** The code validated the current contract metadata for all 20 USDT perpetuals, opened the public depth@500ms and aggTrade combined streams, and fetched all corresponding depth snapshots. It then completed the bounded capture without credentials or orders.

| Check | Observed result |
|---|---:|
| Contracts in cohort | 20 / 20 active USDT perpetuals |
| Capture duration | 125.282 s of 120 s requested |
| Depth events | 4,521 |
| Aggregate trades | 4,997 |
| Per-symbol local-book validity | 100% for 20 / 20 symbols |
| Unexpected reconnects | 0 |
| Segment records / bytes | 9,760 / 10,569,425 |
| Segment SHA-256 + record-count verification | Passed |
| Peak process RSS | 76,251,136 bytes (~72.7 MiB) |
| Total-output rate, linearized | ~304.6 MB/hour |

The observed rate would imply roughly 7.3 GB/day if it stayed constant. That is only a rough extrapolation from a 125-second sample; market activity, event payload mix, reconnects, and compression/rotation policy can materially change the real rate. Size the eventual collector from a multi-hour measurement, not this estimate.

## Limits and decision

- No reconnect was observed or deliberately injected in this run. Reconnection/recovery acceptance is therefore **untested**, not passed.
- Post-run audit found two stale output labels from the original two-symbol pilot: `complete_60m: true` despite only 120 seconds requested, and `observed_both_symbols` despite a 20-symbol cohort. These were naming bugs, not a 60-minute capture or recovery pass. The ignored manifest was corrected to `complete_requested_capture` and `observed_all_symbols`; the collector and regression tests now emit those accurate names. The segment itself was not changed, and its SHA-256/record-count verification still passes.
- Full book validity here measures successful local sequence synchronization during this short capture; it does not establish exchange-side completeness or future availability.
- This stream is a live prospective source. Binance's public historical `bookDepth` archive is not equivalent to tick-by-tick L2: the official archive discussion describes summarized cumulative depth bands rather than true event-level order-book updates. The official repo also documents access restrictions and gaps for its separate historical order-book products. Therefore the historical archive cannot be silently substituted to backtest a depletion/refill rule.
- A report in the official repository issue tracker alleges frozen inner ask bands in some USD-M daily `bookDepth` files since 2026-09-03; this is a reporter's issue evidence, not a Binance-confirmed incident. Any future archive use needs independent per-symbol/date integrity checks.
- This capture is a technical feasibility sample. It was not used to select thresholds and is not an OOS sample. No strategy accuracy, win rate, target-first rate, expectancy, or profitable edge is claimed.
- The next meaningful step is to preregister one fully numeric L2 depletion→refill hypothesis and its baselines before collecting its untouched forward evaluation set. Only the later frozen evaluation can count toward ≥200 non-overlapping OOS events and the ≥80% target-first primary criterion.
- A 2026 study of selective 5- and 10-minute crypto event-contract forecasts reports 58.6–63.3% on its own settlement task at roughly 10–11 trades/day, with costs and multiple-testing controls. That is not a direct comparator to our target-first trading rule, but it is a relevant warning against assuming confidence filtering alone yields 80% precision.

Sources:

- [Binance public-data README](https://github.com/binance/binance-public-data/blob/master/README.md?plain=1)
- [Official repository issue on `bookDepth` semantics](https://github.com/binance/binance-public-data/issues/447)
- [Official repository issue reporting USD-M `bookDepth` band behavior](https://github.com/binance/binance-public-data/issues/496) — reporter claim, not an official Binance acknowledgement
- [Binance public-data order-book download notes](https://github.com/binance/binance-public-data/diffs/0?commit=e8cdb38250d443e8b948f6cf7e37207614a7ad43&name=master&sha1=4d66fc593d6afa301c9266aed28598f8fc76d6a4&short_path=eefa7af&w=false)
- [2026 selective short-horizon crypto event-contract study](https://www.mdpi.com/1999-4893/19/8/704) — different settlement and execution model; metrics are not directly comparable to target-first precision.

## Reproduction and artifacts

- Script: `scripts/research/crypto_l2_pilot.py`
- Run manifest (ignored local data): `chart_predictor/data/crypto_l2_pilots/20symbol-feasibility-20261117/20261117T060240Z-1424c652/manifest.json`
- Segment (ignored local data): `chart_predictor/data/crypto_l2_pilots/20symbol-feasibility-20261117/20261117T060240Z-1424c652/capture.jsonl`
- Input symbols: `BTCUSDT,ETHUSDT,BNBUSDT,SOLUSDT,XRPUSDT,ADAUSDT,DOGEUSDT,TRXUSDT,AVAXUSDT,LINKUSDT,BCHUSDT,LTCUSDT,DOTUSDT,UNIUSDT,NEARUSDT,ATOMUSDT,ETCUSDT,FILUSDT,APTUSDT,ARBUSDT`
- Script SHA-256 recorded in manifest: `b21c8a6b726089ed6a3d68be95c0a69ce1b2a4d50a056e7121556762a96b6b1a`
- The manifest's segment digest is `7e4c8171ddea6e95bf1a7a559ef59e864d9d0d69bb24c4562e89fbd479be588e`; 9,760 records and the digest were re-verified after capture.

## Research portfolio status

- Crypto R034: 0 qualifying OOS strategies; 80% development target-first cells fail the needed evidence gates (see R034 report).
- KR/US: independent domain reviews found current CSV experiments exploratory and the point-in-time delisted/corporate-action/total-return evidence insufficient for the locked OOS pass tests; no qualifying performance claim is made.
- R035 changes the data-collection capability only. It does not promote any crypto candidate or change the KR/US data gate.
