# BTC impulse → altcoin underreaction: fixed development probe

**Decision: reject this candidate as a demonstrated signal.** It did not approach the requested 80% target-first precision, had only 0.41% signal coverage, and produced strongly negative fee-adjusted R. The only small precision improvement was against the fixed random baseline at 10 minutes; it disappeared against the momentum baseline and at 20 minutes, while net R remained worse than both baselines.

## Frozen hypothesis and scope

The rule is preregistered in [`crypto_btc_lead_alt_lag_preregistration_20261115.md`](crypto_btc_lead_alt_lag_preregistration_20261115.md). BTC's 5-minute absolute return must exceed its trailing 30-day 95th percentile; a target alt must underreact relative to a 60-return lagged BTC beta while its prior 15- and 60-minute returns align with BTC. Entry is next-minute open; stop is 1-minute ATR(14), target 2R; no overlapping candidate signals per symbol for 20 minutes. Outcomes use the existing stop-first 1-minute triple-barrier scorer at 10- and 20-minute horizons.

This is a **post-hoc development diagnostic**, not validation. The historical six-symbol database and period have been viewed in earlier research. We used five cached alts against BTC from 2020-01-01 through the exclusive `2026-07-01T00:00:00Z` cutoff; rows at or after the cutoff were not loaded. The dataset is not a point-in-time investable universe and cannot satisfy the required 20-symbol gate. The strategy run itself was repeated twice with identical aggregate outcomes before adding day-cluster uncertainty; both runs produced 67,035 events and identical counts and metrics.

Input database: 19,776,458 candle rows / 6 symbols, `2020-01-01T00:00:00Z` through `2026-06-30T23:59:00Z`; file size 2,558,599,168 bytes; SHA-256 `7e44897a07c67176d5401c23877d0e9e4d6ad5f9acc05efbc7d0cb533082b3e4`. The full input file was fingerprinted, but the experiment query is explicitly `open_ms < 2026-07-01T00:00:00Z`.

## Results

Candidate coverage was 67,035 accepted signals / 16,325,884 eligible alt-symbol minute anchors = **0.4106%**. All signals were scored. `Wilson95` is the naive per-event interval. `Block95` is a post-hoc circular 7-UTC-day moving-block bootstrap (2,000 replicates), retaining cross-symbol observations on sampled dates. It is a descriptive interval, not a final pre-registered inferential test.

Always-flat emits no directional forecasts, so its signal coverage is **0%** and its directional precision is **undefined**; it is not treated as a 0%-accurate strategy. Candidate results by target symbol are below. `T/S/TO` means target/stop/timeout counts; net R is after the 0.10% base round-trip fee and is not an account-level portfolio return.

| Symbol | Events | 10m T/S/TO | 10m precision | 10m net R | 20m T/S/TO | 20m precision | 20m net R |
|---|---:|---:|---:|---:|---:|---:|---:|
| BNBUSDT | 13,762 | 3,946 / 8,561 / 1,255 | 28.67% | −0.840 | 4,404 / 9,080 / 278 | 32.00% | −0.837 |
| DOGEUSDT | 12,849 | 3,573 / 7,921 / 1,355 | 27.81% | −0.590 | 4,044 / 8,450 / 355 | 31.47% | −0.588 |
| ETHUSDT | 13,953 | 3,956 / 8,758 / 1,239 | 28.35% | −0.687 | 4,329 / 9,256 / 368 | 31.03% | −0.684 |
| SOLUSDT | 12,645 | 3,539 / 7,767 / 1,339 | 27.99% | −0.469 | 4,002 / 8,317 / 326 | 31.65% | −0.470 |
| XRPUSDT | 13,826 | 3,792 / 8,532 / 1,502 | 27.43% | −0.637 | 4,279 / 9,152 / 395 | 30.95% | −0.637 |

Per-symbol estimates are exploratory and unadjusted; no symbol has an independent untouched validation period. Every symbol/horizon cell has negative base net R and 30.95–32.00% 20-minute target-first precision.

| Horizon | Target / stop / timeout | Target-first precision | Wilson 95% | 7-day block 95% | Mean net R, base (block 95%) | Mean net R, stress (block 95%) |
|---:|---:|---:|---:|---:|---:|---:|
| 10 min | 18,806 / 41,539 / 6,690 | 28.05% | 27.72–28.40% | 27.54–28.57% | −0.648 (−0.680 to −0.615) | −1.896 (−1.984 to −1.803) |
| 20 min | 21,058 / 44,255 / 1,722 | 31.41% | 31.06–31.77% | 30.90–31.93% | −0.647 (−0.681 to −0.615) | −1.894 (−1.981 to −1.808) |

Costs are 0.10% round trip base and 0.30% stress. The stress case is an explicit fee sensitivity, not a measured account fee. Funding, spreads, slippage, depth, latency, and exchange/account-specific liquidation were not modeled.

## Matched baselines

All baseline directions use the candidate's exact accepted event anchors, entry, absolute stop distance, 2R target, minute path, and horizon. `Δ` is candidate minus baseline. Paired precision intervals use the same 2,000-replicate 7-day UTC moving-block procedure. Net-R difference intervals are also paired; the same fee applies on both sides of a matched event.

| Horizon | Baseline | Baseline target-first | Paired precision Δ (block 95%) | Candidate net R base vs baseline | Paired net-R Δ (block 95%) |
|---:|---|---:|---:|---:|---:|
| 10 min | Fixed-seed random | 27.27% | +0.78 pp (+0.27 to +1.30 pp) | −0.648 vs −0.623 | −0.025 (−0.043 to −0.008) |
| 10 min | Alt 5m momentum | 28.17% | −0.12 pp (−0.26 to +0.06 pp) | −0.648 vs −0.637 | −0.011 (−0.015 to −0.004) |
| 20 min | Fixed-seed random | 31.64% | −0.23 pp (−0.79 to +0.35 pp) | −0.647 vs −0.620 | −0.027 (−0.044 to −0.008) |
| 20 min | Alt 5m momentum | 31.64% | −0.22 pp (−0.42 to −0.04 pp) | −0.647 vs −0.635 | −0.012 (−0.016 to −0.004) |

The 10-minute/random precision contrast is the sole positive paired precision interval among these four dependent comparisons. The strategy was tested on already-exposed development data, multiple dependent horizons/baselines were inspected, and no multiplicity-adjusted significance claim is made. It cannot outweigh the negative net expectancy or establish an edge. The 20-minute precision difference against momentum is approximately −0.22 pp; its reported interval is negative, but that small effect is post-hoc.

## Causal and reproducibility checks

- Feature implementation uses only completed 1-minute candles; beta ends before the five-minute impulse window, and the threshold is computed from the preceding 30 UTC days only.
- The end-to-end feature test mutates all future prices after an anchor and verifies the anchor features remain identical. A deliberate next-close future-peeking negative control changes under the same mutation.
- Discontinuous windows do not generate returns; outcomes require the exact minute path. Entry is next-minute open and ties are stop-first through `score_forecast`.
- Both full replays matched on all outcome aggregates: 67,035 candidate events, 0.4106056% coverage, and exact equal outcome rows at both horizons.
- The fixed exploratory rule count is one. Horizon and matched-baseline comparisons are dependent; no threshold or parameter grid was run.

## Final disposition and next action

**Reject for signal use; do not tune this hypothesis on this same interval.** Its fixed, low coverage does not rescue its 28–31% precision or roughly −0.65 base mean net R. A future experiment would need a new prospective period and a frozen symbol cohort. A broader 20+ symbol result also requires point-in-time listing eligibility and delisting capture. The higher-frequency OFI hypothesis requires archived synchronized depth/trade events; the current candle database cannot test it.

Machine-readable outputs from the two exact runs were kept outside the Git repository at `/private/tmp/crypto_btc_lead_alt_lag_dev_20261115.json` and `/private/tmp/crypto_btc_lead_alt_lag_dev_20261115_clustered.json`; the repository retains the fixed rule, implementation, tests, and this aggregate report, not raw event data.
