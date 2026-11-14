# Addendum A1 — CLV execution and OHLC validation correction

Timestamp: 2026-11-06. Applied after independent code review and before corrected rerun.

## Reason

The first run (`GEN04-20261106T100527-66055`) exposed a runner defect: CLV events that exceeded the `K` concurrent-position cap remained queued and could be selected later, so some event lots would enter after their signal close and hold fewer than the registered five sessions. The CLV signal gate also omitted open-price/high-low consistency, and the simulator checked only open/close validity for held positions. These defects violate the preregistered next-open execution and invalid-OHLC rejection contract.

## Correction

- At each close, preserve active event lots; expire lots whose fifth open-to-close session has ended; among same-close signals, rank only the available slots by CLV descending then ticker. Discard overflow signals completely. A discarded signal is never queued. An accepted close-`t` signal is targeted at opens `t+1` through `t+5`, then exits at open `t+6` unless a distinct post-expiry event occurs.
- Require positive, internally consistent O/H/L/C for each CLV signal bar.
- Use a Gen04 strict execution function that rejects any new/held position on a missing or internally inconsistent O/H/L/C bar.
- Add immutable content fingerprints over the market data files, benchmark/calendar input, and universe/membership input consumed by the local loader.
- Preserve the original attempt ledger and outputs. Treat both original CLV results as invalid mechanics runs, not strategy performance evidence. The original US TEMA attempt and KR TEMA data-gap rejection remain visible. Re-run all four preregistered candidate-market combinations with the corrected runner and new code/data hashes; count them as additional tests, not replacements.

No signal thresholds, market windows, costs, candidate definitions, or performance criteria are changed.
