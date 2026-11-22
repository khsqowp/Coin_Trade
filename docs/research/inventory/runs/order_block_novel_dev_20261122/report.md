# Order-block novel hypotheses — development-only diagnostic

Run date: 2026-11-22. **Disposition: invalid for preregistered validation;
diagnostic only.** This run was executed before its exact rules and envelope
were frozen. The results are preserved as a pilot and cannot be promoted,
called OOS, or reused to select a winning parameter cell.

## Scope and provenance

- Input: `chart_predictor/data/candles.sqlite`, opened with SQLite `mode=ro`.
- SHA-256: `cac23a3d18be66e226bdf8c3dbc0d08f5c6c185d4f18ed2a8687f08d2b6f67b1`.
- Selected development interval: 2026-07-17 00:00 UTC through 2026-10-09 00:00 UTC,
  half-open. This is already-exposed project development data, not OOS.
- All 100 DB symbols were included without a fresh `exchangeInfo.underlyingType`
  filter. Product eligibility is therefore **unverified**; XAUTUSDT appears in
  the output and is not a coin underlying. No coin-eligible-universe result is
  claimed.
- Four reported cells: two hypotheses × H=10/20 one-minute bars. The 136,064
  event rows include the same signal scored at both horizons and heavily
  overlapping signals. They are not 136,064 independent trials.
- Legacy fee assumptions: 10/30 bp round trip. Added slippage sensitivity:
  2/5 bp per side (assumptions only, not measured). Funding archives were not
  available in this runner; funding is omitted, so net expectancy is incomplete.
- The event ledger and summary were written under
  `/private/tmp/ob-dev-full-20261122/`; they are transient and not committed.
  The input DB was not changed.

## Results

| Hypothesis | H (minutes) | Issued outcomes | M2 | Wilson 95% | Per-symbol non-overlap N / M2 | Mean net base / stress* |
|---|---:|---:|---:|---:|---:|---:|
| Breaker retest | 10 | 60,935 | 18.24% | 17.94–18.55% | 53,865 / 18.18% | −0.141% / −0.401% |
| Breaker retest | 20 | 60,927 | 24.74% | 24.40–25.09% | 51,776 / 24.71% | −0.142% / −0.402% |
| HTF first mitigation (5m zone → 1m entry) | 10 | 7,101 | 4.13% | 3.69–4.61% | 6,738 / 4.07% | −0.145% / −0.405% |
| HTF first mitigation (5m zone → 1m entry) | 20 | 7,101 | 9.00% | 8.36–9.69% | 6,693 / 8.95% | −0.140% / −0.400% |

*Funding omitted; net columns subtract only the declared fee and slippage
assumptions. They are not complete futures PnL estimates.

Exit diagnostics:

- Breaker H10: 28,771 stops, 11,117 targets, 20,898 timeouts, 149 invalid
  entries.
- Breaker H20: 34,906 stops, 15,075 targets, 10,797 timeouts, 149 invalid
  entries.
- HTF H10: 1,444 stops, 293 targets, 5,363 timeouts, 1 invalid entry.
- HTF H20: 2,262 stops, 639 targets, 4,199 timeouts, 1 invalid entry.

Per-symbol non-overlap here greedily keeps events whose signal anchors are at
least H minutes apart within each symbol. The pooled Wilson interval is
descriptive only: symbols/time periods remain dependent. Coverage was not
computed in this pilot. The database symbol universe is not point-in-time.

## Failure analysis

1. Both mechanisms miss the fixed M2 >=80% gate by a large margin. Even their
   best H20 cells remain below 25% (breaker) and 9% (HTF mitigation).
2. Stop-first outcomes dominate target-first outcomes. The HTF zone version
   also has very high timeout frequency, indicating weak/slow follow-through.
3. Net expectancy is negative even before funding; including adverse funding
   cannot rescue these displayed assumptions without separate evidence.
4. These metrics are from an unregistered pilot on exposed development data,
   with no verified underlying-type filter and no funding. They cannot establish
   failure on a clean sealed OOS cohort, nor can they establish a usable edge.
5. This run does not justify tuning thresholds against the same interval.
   Current v1 hypotheses are rejected as practical candidates for this exact
   development implementation. Any materially new mechanism requires a new
   preregistration and an untouched forward sample; do not grid-search the
   existing event thresholds on this same dataset.

## Implementation / causal checks

The accompanying implementation has three synthetic tests: breaker prefix
invariance, HTF output/index and stop-side checks, and future-mutation invariance
of zone formation. They passed. These tests validate selected code properties,
not every event timestamp or exchange-specific fill behavior. The full event
ledger should be independently replayed before any future decision.

Reproduction command (writes to a new temporary directory):

```bash
/opt/anaconda3/bin/python3 scripts/research/order_block_novel_dev_probe.py \
  --out /private/tmp/ob-dev-full-20261122
```
