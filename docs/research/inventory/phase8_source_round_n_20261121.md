# Phase 8 — Round N four-source scan, data correction, and pre-score panel

Status: **one frozen historical diagnostic is registered; price outcomes are
not yet scored.** No candidate in this report is a Core. Phase 9 remains
blocked.

## Data correction discovered during continuation

Earlier Round M/H notes described the inspected strategy dataset as hourly and
the current 1-minute archive as unavailable or limited. The NAS path
`/Volumes/home/mac/CODE/trading_data/external/crypto/binance` now contains a
larger Binance Vision archive. The external downloader, its source URLs, and
its manifest were rechecked read-only. Its manifest was being appended during
inspection, so whole-manifest row counts and hashes are snapshots, not frozen
dataset properties. The audit binds this study to the exact 416 selected file
records and their Parquet hashes; unrelated manifest appends are permitted.

For the fixed 2026-07 through 2026-10 window, the manifest describes all 416
required files: 140 contract 1-minute kline files and 140 mark-price 1-minute
files across 35 symbols, plus 136 funding files across 34 symbols. All 416
actual file sizes and SHA-256 hashes matched manifest entries. All 280 monthly
contract/mark files had exactly the expected calendar minute count, strict
60-second increments, and no missing or duplicate timestamps. The signal
scoring universe is frozen to the 34-symbol price/mark/funding intersection;
TONUSDT is excluded before outcomes because its funding files are absent.

The downloader source references official `data.binance.vision` objects,
stores each converted Parquet hash, source URL, and source ZIP byte count, and
checks publisher `.CHECKSUM` values when those responses are available. The
original ZIP hashes and per-download response bodies were not retained.
Current Parquet-to-manifest agreement therefore verifies the selected local
file identity, not independent publisher attestation. The external source
tree remains read-only; this report does not copy or delete data.

## Four independent source lanes

| Lane | Reviewed material | Disposition |
|---|---|---|
| SNS / research | Shanaev et al., [Turn-of-the-candle effect](https://researchportal.northumbria.ac.uk/files/121797908/1_s2.0_S2405844023014433_main.pdf); Kitron and Wengrowicz, [short-horizon reversal](https://arxiv.org/abs/2608.21888) | Do not retest the 15-minute boundary effect: registry #23 already has six-symbol M2 results around 47–49% and negative cost-proxy net returns. The short-horizon reversal is both structurally overlapping and source-reported gross edge (~1.3 bp) below the cited 5 bp round-trip cost. |
| TradingView / Pine | [Delta Pulse and CVD Pine v6](https://github.com/Robwhitlow3/tradingview-orderflow-indicators) | No eligible new setup. The signals use lower-timeframe/order-flow approximations and confirmed pivots that can be drawn back on earlier bars; the relevant CVD/taker families already exist in the registry. Pine source/license inspection does not establish M2 value. |
| Public communities | [Absorption discussion](https://www.reddit.com/r/OrderFlow_Trading/comments/1olfp00/absorption_advice/) and a public mark-price explainer | No complete candidate. The absorption setup needs footprint/delta or book evidence not present in the audited archive; the mark-price explainer has no fixed signal/barrier recipe. |
| GitHub / skills | [quant_experiments](https://github.com/jshekhawat/quant_experiments), [Algo-Trading-Skills](https://github.com/HimanshuJ16/Algo-Trading-Skills) | No reusable eligible strategy. The minute breakout, volume, taker/CVD, and funding filters overlap earlier families; one repository's reuse license was not verified. The skills repository is implementation guidance, not a complete directional M2 strategy. |

The scan also considered a source-inspired pre-funding settlement direction.
It was rejected: the reviewed hourly result does not establish a reliable
minute-scale directional edge, and historical funding event time is not the
same thing as point-in-time signal availability.

## Blind four-role panel

The panel reviewed candidates without opening market-price outcomes.

| Candidate | Blue | Red | Data / Methods | Judge | Decision |
|---|---|---|---|---|---|
| 15-minute candle-boundary effect | Reject after registry duplicate confirmed | Reject | Not equivalent to a source replication; existing probe is exposed | Initially conditional | Reject; no rerun of registry #23 |
| Contract-close / mark-close deviation mean reversion | Conditional pass for one diagnostic | Conditional pass for one diagnostic | Pass after fixed-seed bootstrap and target-manifest append handling corrections | Pass for a one-time diagnostic | Proceed only after the completed preregistration and synthetic checks; not Core/OOS |
| Pre-funding settlement direction | Reject | Reject | Ineligible absent point-in-time funding availability and complete fixed rule | Reject | Reject |

The selected candidate is a custom hypothesis, not a source-paper
reproduction and not proven alpha. The exact rule, fixed universe, 2026-07-01
through 2026-11-01 interval, costs, target/stop ordering, baselines, score
gates, and no-retuning rule are recorded in
`PREREG_MARK_DEVIATION_M2_20261120.md`. This period is historical and overlaps
dates used for earlier hourly strategy research. Candidate-specific minute
candidate outcomes were not scored before this preregistration, so the planned
run is a limited historical diagnostic, not pristine OOS evidence. The
pre-score audit reads OHLC fields only for finite-value and candle-invariant
checks; it does not calculate signals, barriers, or outcomes.

## Frozen test status

- One candidate; H=10 minutes is primary and H=20 is a fixed secondary.
- Signal: completed-minute `ln(contract_close / mark_close)` z-score crossing
  ±2 against the previous 60 completed values; next-minute contract open
  proxy; equal 1× prior 14-bar ATR target and stop; per-symbol 20-minute
  lockout.
- Evaluation: contract OHLC target-first; stop-first same-candle collision;
  adverse stop gap; no target price improvement; timeout is a failure.
- Costs: legacy 10 bp / 30 bp round-trip fee proxies plus realized funding if
  a settlement falls in the holding interval. These do not include measured
  spread or slippage.
- Synthetic unit tests pass 11/11 after review corrections (bootstrap seed,
  complete-calendar block sampling, per-symbol outcome fields, funding timestamp
  jitter, and live-manifest append handling). The 2026-11-21 read-only preflight
  passed: 416/416 target hashes and byte sizes match, 280/280 price files have
  exact minute grids, and 34 funding series pass timestamp/interval checks.
  The manifest had 13,648 rows in that snapshot; its whole-file SHA-256 was
  `69ddfb9...96997`, unchanged during this audit. Target-file fingerprint:
  `7a1f9dd...b3095c`. No backtest result exists in this report.
- If the diagnostic is run, all primary thresholds are applied as registered.
  A failed rule is rejected without tuning. A passing historical diagnostic
  still requires a separate red-team review, robust sequential evidence, and
  forward paper observations before any Core decision.

## Limits and source links

No Pine, GitHub, or community code was installed or executed. No external
performance claim was used as a local score. This is a bounded source screen,
not proof that all strategies have been searched. There is no BBO, validated
point-in-time OI, or liquidation feed in this archive; no claim of actual
fills, live execution, or 80% accuracy is supported before the registered run.
