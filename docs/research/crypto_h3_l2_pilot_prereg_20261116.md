# Crypto H3 L2 order-book confirmation pilot — preregistration

Date: 2026-11-16 (Asia/Seoul)  
Status: frozen before computing H3 outcome metrics; descriptive development pilot only.

## Question

Does the existing H3 rule—persistent top-five depth imbalance followed by same-direction mid-price confirmation—show short-horizon directional information in the newly captured BTCUSDT/ETHUSDT public L2 stream? This is a mechanism screen, not an evaluation against the project's M4 approval gate.

## Data and scope

- Frozen input: `chart_predictor/data/crypto_l2_pilots/20261116T025255Z-cc3a1f96/capture.jsonl`.
- Capture SHA-256: `aff87b771f2494fdc70ccc424e0a383f32670183d9753a83e68a92b9ebb1a991`.
- Universe is exactly BTCUSDT and ETHUSDT; capture target is one hour. The sample is not a point-in-time 20-symbol universe and is not a sealed holdout.
- Use the captured synchronized depth snapshots/deltas and aggregate trades. Preserve receive-monotonic ordering. Exclude every invalid-book interval and any sequence gap until snapshot bridging restores a valid book. Do not interpolate across invalid intervals.
- Use USDⓈ-M `PRICE_FILTER.tickSize` metadata sampled before the capture on the same UTC date (`serverTime=1794795462361`, 2026-11-16T02:17:42Z): BTCUSDT `0.10`, ETHUSDT `0.01`. Do not substitute `pricePrecision`.

## Frozen signal rule

1. Reconstruct each valid local book with `LocalBook`; compute top-five imbalance after each valid depth update as `(sum(top5 bid quantities) - sum(top5 ask quantities)) / (sum(top5 bid quantities) + sum(top5 ask quantities))`. If either side's top-five total is zero, the update is ineligible.
2. A long candidate requires imbalance strictly greater than `+0.60` on three consecutive sequence-valid depth updates for that symbol. A short candidate requires imbalance strictly less than `-0.60` on three consecutive sequence-valid updates. Reset the streak on an opposite/neutral update, invalid book, disconnect, or sequence error.
3. After the third update, require the first same-direction mid move of at least one symbol tick within the next 1.000 seconds. The move is measured from the mid at the third imbalance update. No confirmation means no signal. Signal/entry timestamp is the receive-monotonic timestamp of the confirming depth update; entry reference is that update's mid.
4. To avoid overlapping outcomes, accept at most one event per symbol until five seconds after its confirmation. Do not tune thresholds, time windows, or cooldowns on this capture.

## Outcomes and comparisons

- Primary descriptive outcome: side-correct mid-price markout at 1, 3, and 5 seconds after confirmation. For each horizon use the first valid book update at or after the requested horizon and no later than one additional second; otherwise label the horizon unscorable. A zero markout is not a hit.
- Execution-cost diagnostic: hypothetical immediate crossing at the observed best quote (long enters ask/exits bid; short enters bid/exits ask) at the same event and horizon quote timestamps, less the frozen 0.10% round-trip fee. This is not a fill simulation; it omits queue position, market impact, latency after local receive, and deeper size consumption.
- Same-event price-only comparator: direction of the valid mid-price move over the one second immediately before confirmation; zero prior move abstains. Also report a fixed-seed random-side diagnostic on the same event rows. These are screening comparators, not the complete registered M4 baselines.
- Report signal counts, per-symbol and per-horizon hit/net-markout results, eligible-book-time coverage, valid/invalid time, and exact unscorable counts. Do not pool the two symbols as independent replicas or claim calibrated probabilities.
- Trial accounting: one frozen H3 pilot on one capture. No parameter grid or post-result tuning.

## Causal and integrity checks

- Feature values for the three-update imbalance streak use only the local book available at each update. Confirmation is itself a later trigger event; the forecast starts only at that confirmation, and markout begins afterward.
- Reconstruct depth with snapshot bridge and `pu == previous update ID`; sequence errors invalidate the book. Preserve a fail-closed state until the next valid snapshot bridge.
- Validate input SHA-256, every JSONL row's parse, event-order monotonicity per stream, and output row counts. Unit-test strict threshold comparisons, reset behavior, tick confirmation, confirmation timeout, gap invalidation, horizon lookup, and overlap suppression with synthetic events.
- The capture includes a controlled client-side disconnect. Its invalid interval is excluded; it is not treated as an outcome or filled forward.

## Pre-result implementation QA

- Official public `exchangeInfo` returned `serverTime=1794795462361` (2026-11-16T02:17:42Z), BTCUSDT status `TRADING` / tick `0.10`, and ETHUSDT status `TRADING` / tick `0.01`. Binance's [USDⓈ-M Exchange Information documentation](https://developers.binance.com/en/docs/catalog/core-trading-derivatives-trading-usd-s-m-futures/api/rest-api/market-data) identifies `PRICE_FILTER.tickSize` as the tick field and explicitly warns not to treat `pricePrecision` as tick size.
- Hash/structure-only replay before signal scoring matched the frozen input hash and parsed 121,098 JSONL rows. It observed 14,311 depth deltas, four recorded snapshots, two invalid-book transitions, four valid-book transitions, zero sequence/bridge errors, and 7,155 reconstructed quotes per symbol (including one snapshot-bridge quote per symbol).
- Eight synthetic unit tests pass before running the frozen signal rule. These checks validate semantics only; they are not strategy outcomes.

## Decision limits

This 2-symbol, 1-hour development pilot cannot satisfy the 20-symbol/N≥200 sealed M4 gate, establish a calibrated ≥80% signal, estimate day-clustered uncertainty, or demonstrate profitability. Even a strong descriptive markout is only a reason to design a fresh prospective multi-symbol recording; a weak/negative result rejects this fixed H3 screen for this pilot but does not prove all order-flow methods fail. No trading orders or API credentials are in scope.

## Pre-result protocol amendment — 2026-11-19

The outcome file was verified absent before this amendment. No H3 signal outcomes or markout scores had been computed or inspected when it was made.

- The original five-second cooldown could admit a new event exactly when the prior five-second label's permitted one-second-late quote was still valid. This leaves touching/overlapping outcome intervals.
- Change the per-symbol cooldown from 5.000 to **7.000 seconds after confirmation**. Since each label uses a quote no later than horizon +1 second, this leaves at least one full second between the latest permitted quote for an accepted event and the next event's entry.
- This is an integrity amendment prompted by independent pre-result review, not an outcome-driven parameter optimization. No imbalance, confirmation, horizon, universe, fee, comparison, or scoring rule changes. Report the amended protocol as `H3-L2-pilot-v1.1-amended-2026-11-19` and retain this original registration and amendment history.
- Before scoring, hard-pin the input path to `chart_predictor/data/crypto_l2_pilots/20261116T025255Z-cc3a1f96/capture.jsonl`, manifest run ID to `20261116T025255Z-cc3a1f96`, and SHA-256 to the frozen value above; do not expose a CLI override for those registered inputs. Require the sibling manifest's complete segment path, byte count, and row count; parse every newline-terminated JSONL row; validate receive-monotonic ordering across both depth and aggregate-trade connection/data records; and report manifest valid/invalid book time and per-symbol unscorable counts. Synthetic tests must cover these checks, horizon grace, zero markout, long/short fee arithmetic, and score-count invariants.
