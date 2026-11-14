# US-30 - 10-day drop with volume at own 250-day low percentile (KR-26b analogue) (US, Round 5 prereg)

## Signal (fixed defaults)
Signal at close t: close_t/close_{t-10}-1 <= -15% AND volume_t <= 30th percentile of volume over bars t-249..t. Buy close t, sell close t+3. F14-300, F18-300 (2 trials).

## Common (Round 5 US hypotheses; written 2026-11-13 BEFORE any run of them)
- Origin: KR-session ledger (KR-24 post-crash rebound, +1.42% net t=2.29 in KR; KR round 3 designs KR-25..27) and coordinator request for a US-18 horizon sweep. Ideas from KR ledger text and first principles only; no holdout information used.
- Crash analogues (US-28..31): universes F14-300 / F18-300 = top-300 names by lib value20 on 2014-12-31 / 2018-12-31, frozen (events from the next bar). Top-300 instead of top-100 because large-cap crashes are rare. Residual bias: members are current S&P 500 constituents; for crash-rebound ideas this survivorship bias is SEVERE (crashed names that never recovered and left the index are absent) and results are discounted accordingly. US thresholds are scaled down vs KR (-10..-12% instead of -15..-20%) for large caps. Buy close t, sell close t+3. Cost USCost RT 0.403%; 2x, 3x, next-open reported.
- Verdict rule: PLAN Stage 1 (net>0, clustered t>=3, both halves>0; halves = midpoint of each universe's event window). Survivors enter Stage 2 only with top-5 symbol share <= 40% and dev 2x-cost mean > 0. Trials join the cumulative BH list (112 so far incl. Stage 2 grid cells).
