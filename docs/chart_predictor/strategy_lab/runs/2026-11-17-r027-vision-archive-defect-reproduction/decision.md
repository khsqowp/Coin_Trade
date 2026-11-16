# R027 decision

**Decision: REJECT these Vision metrics archives as an unqualified complete feature panel; continue only with explicit per-field/per-time coverage masks.**

- The BTC/ETH metrics data for 2024-02-16 omit the final 125 five-minute rows; this prevents using any metrics field during that interval.
- BTC/ETH mark-price 5m archives on 2023-11-10 each omit the same five timestamps. These exact gaps remain despite checksum validity.
- On 2025-07-22, the full timestamp grid is present, but `count_toptrader_long_short_ratio` is empty for 30 rows per symbol. Row-count-only completeness checks are insufficient.
- The issue's duplicate samples (2024-04-08 and 2024-05-01) were not reproduced in the current ZIPs. The reported 2025-07-22 missing timestamps were also absent in the current ZIPs, though a top-trader-count field gap remains.
- This small date/symbol sample cannot establish archive-wide rates, the date of any repair, or an OI timing rule. No trading strategy was tested.

Before any metrics-based performance trial, the exact symbol/date/field input manifest must be frozen and audited for checksum, missing timestamps, duplicates, off-grid points, null/non-finite values, and causal availability. Preserve gaps; do not fill them. The OI candidate remains unregistered and unscored, and the overall crypto target-first-qualified count remains 0.
