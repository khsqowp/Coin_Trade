# Dedupe notes

Collection scope: community sources only. No existing archive files were present under `strategy_archive/` when inspected; the separately owned `github_tv/` path was not accessed or changed. Existing user-specified exclusions were applied: BB+Stoch+STC, momentum rotation, funding arbitrage, and TRX golden-cross.

Deduplication decisions:

- BTC MAX and MIN rules use the six explicit lookbacks (5, 10, 20, 30, 40, 50 days) that the QuantPedia article individually enumerates. These are parameterized variants of a common rule, retained as separate configurations because each has an independently testable lookback. They are not counted as six unrelated concepts.
- `btc-max10-nyse-close` and `btc-max10-overnight-selected` are distinct execution schedules (one-night daily hold versus selected overnight intervals) sourced from the overnight article.
- `btc-min-max-10d` records the explicitly reported combined extrema construction. Entry/exit details are incomplete and flagged accordingly.
- Forum and Reddit rules are kept separate when their entry variables, thresholds, or exit timing differ. No generic textbook versions were added.

All rules are paraphrased. Self-reported results are labeled as claims and retain selection, survivorship, costs, or execution caveats where the source disclosed them.
