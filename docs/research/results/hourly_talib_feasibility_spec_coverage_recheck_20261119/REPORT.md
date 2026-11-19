# Hourly TA-Lib pattern feasibility screen

**Outcome-blind frequency screen only. No M2 outcomes or future price paths were read.**

- TA-Lib: Python 0.6.5 / core 0.6.4 (Aug  7 2025 19:49:51)
- Window: [2021-01-01T00:00:00Z, 2026-11-01T00:00:00Z)
- Cohort: 86 archive-manifest symbols; all manifest rows=5522; research-range manifest rows=5522; manifest SHA-256=63dd2082c07279f4e2aa8b36df5b6a8dd17512a097f1f4babb73e4a9ef97d45d
- Present-manifest symbol/month row-count check: expected=241,389,061, observed=241,389,061, count check=PASS; absent scheduled symbol-months=498 are explicitly unavailable (check does not verify archived-file SHA-256 or row content)
- Scheduled symbol-hours: 4,396,320
- Complete hourly bars: 4,023,147 (91.5117% of scheduled slots)
- Feature-eligible anchors: 3,999,307
- Individual claims passing all frequency gates: 0 / 110; maximum individual scheduled coverage=3.174%; feature-eligible diagnostic=3.489%
- Post-hoc union claims passing all frequency gates: 2 / 6
- Same-hour collisions: {"opposing_direction_same_hour": 134967, "same_direction_multi_long": 80760, "same_direction_multi_short": 46301}

Individual pattern rows are preregistered. `ANY:` rows are post-hoc, deterministic unions added after individual frequency counts; they are exploratory and not independent or confirmatory evidence. Any pass only permits a separate, prospectively preregistered performance study. This exposed development panel cannot be confirmatory OOS.
See `claims.csv` for all directional claims and both deadlines; see `summary.json` for the frozen input identity. The `ANY:` union rows are the only exploratory aggregates.

| Exploratory union | Side | Deadline | Signals | Scheduled coverage | Feature-eligible coverage | Non-overlap N | Symbols | Frequency gate |
|---|---:|---:|---:|---:|---:|---:|---|
| ANY: all 30 bullish reversal patterns | long | 10h | 435,413 | 9.904% | 10.887% | 140,154 | 86 | FAIL |
| ANY: all 30 bullish reversal patterns | long | 20h | 435,413 | 9.904% | 10.887% | 84,668 | 86 | FAIL |
| ANY: all 25 bearish reversal patterns | short | 10h | 396,498 | 9.019% | 9.914% | 128,372 | 86 | FAIL |
| ANY: all 25 bearish reversal patterns | short | 20h | 396,498 | 9.019% | 9.914% | 77,732 | 86 | FAIL |
| ANY: two-sided bullish+bearish union | both | 10h | 831,911 | 18.923% | 20.801% | 266,666 | 86 | PASS |
| ANY: two-sided bullish+bearish union | both | 20h | 831,911 | 18.923% | 20.801% | 155,890 | 86 | PASS |

Frequency-eligible claims:

- ANY: two-sided bullish+bearish union (both), 10h
- ANY: two-sided bullish+bearish union (both), 20h
