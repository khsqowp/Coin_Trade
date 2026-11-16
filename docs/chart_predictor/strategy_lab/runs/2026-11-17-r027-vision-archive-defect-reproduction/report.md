# R027 — Current Vision archive defect reproduction

**Finding: the current archive set is mixed. Some reported defects remain; some are not reproduced; one allegedly repaired date has a field-level gap despite a full timestamp grid.** All ten ZIPs matched their adjacent publisher SHA-256 checksums. This is an archive-quality finding, not a signal or performance result.

## Results

| Archive sample | Rows / unique timestamps | Timestamp grid | Field completeness | Result |
|---|---:|---|---|---|
| BTCUSDT metrics, 2024-02-16 | 163 / 163 | 125 of 288 UTC 5m slots missing, 13:35–23:55 | Rows are absent, so all metrics fields are unavailable over that interval | Defect reproduced |
| ETHUSDT metrics, 2024-02-16 | 163 / 163 | 125 of 288 UTC 5m slots missing, 13:35–23:55 | Rows are absent, so all metrics fields are unavailable over that interval | Defect reproduced |
| BTCUSDT mark price, 2023-11-10 | 283 / 283 | 5 slots missing: 03:40, 03:45, 03:50, 03:55, 04:00 | No blank/non-numeric values among present rows | Defect reproduced |
| ETHUSDT mark price, 2023-11-10 | 283 / 283 | Same five slots missing | No blank/non-numeric values among present rows | Defect reproduced |
| BTCUSDT metrics, 2025-07-22 | 288 / 288 | Complete, no duplicates or off-grid timestamps | `count_toptrader_long_short_ratio` blank in 30 rows from 13:40–16:05; other sampled columns populated | Timestamp gap not reproduced; field gap found |
| ETHUSDT metrics, 2025-07-22 | 288 / 288 | Complete, no duplicates or off-grid timestamps | `count_toptrader_long_short_ratio` blank in the same 30 rows; other sampled columns populated | Timestamp gap not reproduced; field gap found |
| BTCUSDT metrics, 2024-04-08 and 2024-05-01 | 288 / 288 each | Complete, no duplicates or off-grid timestamps | No blank/non-finite fields | Reported duplicate timestamps not reproduced in these current objects |
| ETHUSDT metrics, 2024-04-08 and 2024-05-01 | 288 / 288 each | Complete, no duplicates or off-grid timestamps | No blank/non-finite fields | Reported duplicate timestamps not reproduced in these current objects |

The current 2025-07-22 object does not match the issue's reported 34 missing timestamp rows: it now has all 288 timestamp rows, while the top-trader count field is blank for 30 rows. This is evidence that this particular object differs from the issue snapshot or its reported aggregate; it does not establish when or why it changed. The 2024-02-16 and 2023-11-10 defects remain in current checksummed objects.

## Interpretation and limits

- A valid SHA-256 proves byte integrity against the publisher's checksum, not timestamp completeness or field validity.
- The audit reproduces two concrete current gaps for BTC/ETH and a field-specific missing interval on one later date. It does not validate the issue's three-year aggregate missing/duplicate counts.
- Duplicate timestamps alleged for 2024-04-08 and 2024-05-01 were not found in the current sampled ZIPs. That does not prove no duplicates exist on other dates or that prior versions had none.
- The 2025 missing values are in `count_toptrader_long_short_ratio`; they must remain missing. Do not fill them or silently substitute another field.
- R026's +5-minute OI/taker availability findings remain limited to the sampled dates/fields. R027 establishes no broader timestamp convention, strategy edge, target-first precision, or OOS result.
- Crypto signal qualification remains 0. Do not use this archive audit to promote the conditional OI candidate or reopen previously rejected performance cells.

## Reproduction

```bash
python3 scripts/research/audit_vision_daily_archive.py --interval-minutes 5 \
  /private/tmp/r027_binance_archive_repro/*.zip
```

The script reads local ZIPs and checksums, makes no network calls, and emits per-file grid and field-quality counts. Input hashes and compact results are in [`results.json`](results.json).
