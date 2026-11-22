# Slice 4 harness issues

No new issues beyond plugins/slice_3/HARNESS_ISSUES.md (timestamps dropped on slices, no same-bar reversal, next-open fills for stop entries, null cost). Additional observation: `_utc_index` length-matching from BTC is unreliable for symbols with different history length (daily bars); slice-4 plugins match against each symbol parquet instead.
