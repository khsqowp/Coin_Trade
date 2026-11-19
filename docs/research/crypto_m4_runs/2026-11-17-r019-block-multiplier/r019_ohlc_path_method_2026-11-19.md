# R019 synthetic OHLC path-method validation

This is a synthetic mechanics test only. No historical or live market rows or outcomes were read.

- Python / NumPy: 3.13.5 / 2.2.6
- Seed: 20261127
- Scenarios: 8000 / 8,000
- Cost evaluations: 16000 / 16,000
- Mismatches / errors: 0 / 0
- Independent aggregation mismatches: 0
- Sentinels: 17 / 17
- Result digest: `b9a4a0e0f1557b1dabb1c9cfd4cd4d8dd9cde8257eb67cf30d88468f872b64e3`
- Repeat-run aggregate JSON comparison: `cmp -s` exited 0; both files have SHA-256 `9e9261f553d7dad9b32cb03b859982aaf3c9dfc4b84a5f44a827f2838af9bb36`.

## Fixed-case results

| Case | Actual | Oracle | Both match |
|---|---:|---:|---:|
| long_adverse_gap | True | True | True |
| long_favorable_gap | True | True | True |
| long_tie_stop_first | True | True | True |
| long_timeout | True | True | True |
| long_no_fill | True | True | True |
| long_stop_entry_gap | True | True | True |
| long_invalid_stop | True | True | True |
| long_malformed | True | True | True |
| long_stop_entry_malformed | True | True | True |
| long_duplicate_time | True | True | True |
| long_missing_t1 | True | True | True |
| long_missing_t5 | True | True | True |
| long_missing_t10 | True | True | True |
| short_adverse_gap | True | True | True |
| short_favorable_gap | True | True | True |
| short_tie_stop_first | True | True | True |
| short_stop_entry_gap | True | True | True |

## Interpretation

A pass validates only tested synthetic path and cost arithmetic. It does not establish market performance, real execution quality, or signal accuracy.

## Source SHA-256

- engine: `5eafb0008ed62c9cbf8e6be4038b1a0a71bb6df29f70e2d1c157842cbfc84039`
- oracle: `60ce01e5339e51f6fcdafd8e30da8ba48a9bd9e0df6a103c06fedee13bdfad51`
- runner: `e714f71294d21573bec6a2896563922bccb40c7cf6974f2f4fd51d6acac42c47`
