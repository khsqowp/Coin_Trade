# R027 handoff

1. Current Binance Vision archives reproduce the 2024-02-16 BTC/ETH metrics truncation and 2023-11-10 BTC/ETH 5m mark-price gap, with valid publisher checksums.
2. The current 2025-07-22 metrics archives have complete timestamp rows but 30 blank `count_toptrader_long_short_ratio` values per symbol. Do not treat row completeness as feature completeness.
3. Current 2024-04-08 and 2024-05-01 metrics ZIPs have no duplicate timestamps; the issue's duplicate claim is not reproduced for these current objects.
4. No strategy outcome, OOS event, or signal was evaluated. Overall counts remain KR 0, US 0, crypto target-first qualified 0.
5. The next crypto action should be a frozen, per-field, per-symbol archive-coverage audit on only the candidate panel and dates needed by a preregistered hypothesis; continue blocking performance tests that require incomplete inputs.

Files used for independent reproduction are temporary under `/private/tmp/r027_binance_archive_repro/`; they were not added to Git.
