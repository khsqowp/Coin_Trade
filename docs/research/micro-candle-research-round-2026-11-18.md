# Micro-candle research round — 2026-11-18

## Decision

No crypto signal qualifies. The one-bar close-location continuation rule is below its fixed-seed random M1 comparator; the proposed three-bar pullback breakout fails the 10% coverage gate and overlaps the previously tested R021 re-entry-breakout family; the next two-bar expansion/compression hypothesis also fails the coverage gate at the outcome-blind stage. No M2 target/stop outcomes were opened for either new multi-bar candidate. No rule was tuned or inverted after seeing a result.

This is an exploratory development report, not a sealed OOS result, trading recommendation, or deployment approval.

## Scope and data

- Read-only database: `chart_predictor/data/vision_pit_dev_sample.sqlite` (30,363,320,320 bytes; modified 2026-11-17 05:18:39 local).
- Six-symbol diagnostic cohort: BNBUSDT, BTCUSDT, DOGEUSDT, ETHUSDT, SOLUSDT, XRPUSDT.
- Observed cohort bounds: 2021-01-01 00:00 UTC through 2026-10-31 23:59 UTC; 18,345,600 rows.
- For those six symbols, the fixed audit found zero invalid OHLC rows and zero off-minute-grid rows. The source's broader 86-symbol population was not validated by this six-symbol audit.
- Three-candle and 21-candle feature opportunities additionally required contiguous minute spacing. The 21-candle feasibility query required all 21 OHLC rows to pass the validity check.
- These dates and symbols have prior research exposure. The sample cannot act as independent confirmation. The diagnostic work reported M1 and event frequency only; no live orders, funding PnL, fee-adjusted M2 result, WFA, trade-order Monte Carlo, or parameter plateau was evaluated.

## One-candle close-location direction diagnostic

Frozen rule: after a completed one-minute candle closes in the upper 20% of its high-low range, predict UP for the next completed 1-minute close; after it closes in the lower 20%, predict DOWN. Other bars do not emit a forecast. Forecasts are scored only when the next candle begins exactly one minute later. Exact unchanged close is a non-hit for the all-issued score.

| Measure | Result |
|---|---:|
| Eligible anchors | 18,343,539 |
| Issued forecasts / coverage | 9,989,694 / 54.46% |
| Correct forecasts | 4,622,886 |
| All-issued M1 accuracy | 46.2766% |
| Non-flat next-close directional accuracy | 48.3211% |
| Same-anchor one-bar momentum accuracy | 44.9263% |
| Fixed SHA-256 random-side accuracy | 47.8764% |
| Candidate minus momentum | +1.3503 pp; 7-day shared-date block 95% interval +1.2426 to +1.4575 pp |
| Candidate minus random | −1.5998 pp; 7-day shared-date block 95% interval −1.7819 to −1.4254 pp |
| Candidate non-flat directional score | 48.3211%; 7-day shared-date block 95% interval 48.1315% to 48.5046% |

The same-anchor momentum comparator predicts the sign of the signal candle's close minus open. The random-side comparator is deterministic per `(seed, symbol, anchor timestamp)` using the low bit of SHA-256 with seed `20261118`. Uncertainty uses 2,000 circular resamples of shared UTC-date blocks of length seven, seed `20261118`; each replicate contains exactly the original 2,130 dates, and every resampled date carries the aggregate for all six symbols. The paired candidate-minus-momentum interval is +1.2422 to +1.4577 pp; candidate-minus-random is −1.7808 to −1.4266 pp. These are descriptive intervals for an exposed sample and are not multiplicity-adjusted. The rule beats the weak same-anchor momentum baseline, but loses to the fixed random comparator. It does not establish an M2 edge.

## Three-bar impulse / pullback / confirmation feasibility

Outcome-blind fixed rule: bar `t-2` bullish, bar `t-1` bearish with range no more than half of `t-2`, and bar `t` closes above `t-1` high; short is mirrored. All three bars must be one-minute contiguous.

| Symbol | Eligible anchors | Long events | Short events |
|---|---:|---:|---:|
| BNBUSDT | 3,067,198 | 26,686 | 26,007 |
| BTCUSDT | 3,067,198 | 31,960 | 30,977 |
| DOGEUSDT | 3,067,198 | 18,347 | 18,640 |
| ETHUSDT | 3,067,198 | 27,250 | 26,787 |
| SOLUSDT | 3,059,994 | 19,123 | 18,848 |
| XRPUSDT | 3,016,792 | 15,929 | 16,616 |
| **Total** | **18,345,578** | **139,295** | **137,875** |

Coverage is 277,170 / 18,345,578 = **1.5108%**, well below the 10% gate. R021 already tests a pullback followed by a three-bar close breakout; although its funding/macro conditions differ, this candidate is structurally adjacent and cannot be represented as a novel mechanism. No future outcome was queried. **Decision: reject before performance evaluation.**

## Phase-2 two-bar expansion/compression feasibility

This rule was frozen in [the preregistration](micro-candle-phase2-prereg-2026-11-18.md) before its feasibility query. On each completed minute `t`, it requires 21 contiguous valid bars, the median range `M` of `t-20...t-1`, `range(t-1) >= M`, and `range(t) <= 0.5M`. Direction is the color of `t-1`; no outcome path is used in the feasibility stage.

| Symbol | Eligible 21-bar anchors | Long events | Short events |
|---|---:|---:|---:|
| BNBUSDT | 3,067,180 | 62,415 | 57,700 |
| BTCUSDT | 3,067,180 | 68,979 | 66,355 |
| DOGEUSDT | 3,067,180 | 43,466 | 41,219 |
| ETHUSDT | 3,067,180 | 51,788 | 49,510 |
| SOLUSDT | 3,059,940 | 38,380 | 37,199 |
| XRPUSDT | 3,016,720 | 50,199 | 47,694 |
| **Total** | **18,345,380** | **315,227** | **299,677** |

The 614,904 events span all six symbols, but coverage is only **3.3518%** of valid eligible anchors. The preregistered rule says to reject below 10%; therefore no M2 prices were read and no broader-universe expansion was run. This is a feasibility rejection, not a claim that its conditional M2 would be low.

## Four-role agent review

| Role | Output | Evidence boundary |
|---|---|---|
| Korea equity | First-30-minute post-open gap/reaction study is not testable from daily-only data; PIT membership, delisted names, intraday prices, and corporate-action provenance are missing. | Design/readiness assessment only; no outcome test. |
| US equity | Earnings-surprise continuation requires timestamped releases, pre-release point-in-time consensus, PIT universe, delisted names, and verified adjustments. | Design/readiness assessment only; no outcome test. |
| Crypto micro | Proposed a one-minute expansion-then-compression hypothesis, with next-bar direction from the expansion bar. | Feasibility was checked locally; coverage failed. Agent did not inspect local outcomes. |
| Red team | Reinforced all-issued denominators, separate non-overlap samples, causal entry, costs, and a forward sealed sample. | Supplied-context review only; agent could not access local files. |

The agents were given bounded questions and supplied facts. Two could not inspect the repository directly; their outputs are not independent repository audits. Local source and data checks in this report were run by the primary process.

## Data-cleanup checkout state

The primary checkout `/Users/user/CODE/Coin_Trade` still has five modified tracked files and fifteen new files related to data quality, collection provenance, repair, and tests. Those are user-owned uncommitted changes and were not edited, staged, or merged here. The separate research worktree already contained about 15,002 unrelated untracked panel/run files before this round; they were preserved. This report does not claim those files have been fully inventoried or cleaned.

## Reproduction

From the Coin_Trade research worktree:

```bash
python3 chart_predictor/micro_candle_exploration.py --db chart_predictor/data/vision_pit_dev_sample.sqlite
```

The script opens the database in SQLite read-only mode. It runs the fixed one-bar M1 diagnostic with same-anchor momentum and SHA-256 random comparators, shared-date bootstrap, and outcome-blind multi-bar feasibility counts. It does not calculate M2, change the input database, or place orders.

## Next research action

Do not tune these thresholds or invert the one-bar result. The next crypto iteration must start with a pre-registered micro hypothesis that is structurally distinct from the tested candle-reversal, BB-squeeze, pullback/re-entry, and direction-persistence families. Run signal-frequency and symbol-dispersion checks first; open the target/stop paths only if every hard feasibility gate passes. For KR/US, obtain and validate the missing point-in-time intraday datasets before proposing return statistics. A qualifying sealed/forward result remains absent.
