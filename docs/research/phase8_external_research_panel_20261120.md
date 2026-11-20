# Phase 8 external strategy research and panel review

## Cross-asset lead-lag follow-up (2026-11-20)

Two primary-study leads point in opposite directions: Jia et al. (2023) report
negative cross-coin predictability (the “seesaw” effect), while Guo et al.
(2024) report positive Binance cross-cryptocurrency return predictability.
These are research hypotheses, not evidence that a simplified hourly rule is
tradable. A fixed, equal-weight BTC/ETH/XRP/LTC one-hour leader-basket fade was
therefore preregistered and tested on the verified 36-symbol 1h archive (32
targets, H=1 and H=4). Four roles independently reviewed the initial v2. Red
team and methods review found that its H4 bootstrap block counted 168 four-hour
observations (28 days), its coverage/non-overlap summary was incomplete, and
some promised boundary tests were absent. The v3 correction fixed those issues;
second-round red team then identified circular block joins and unresolved
funding-at-exit timestamp semantics. v4 now uses non-circular moving blocks
(168 H1 or 42 H4 anchors per 7 days) and reports both inclusive and exclusive
exit-timestamp funding results. Signal rules were not changed across versions.

The v4 run emitted 1,118,560 event rows. H1/H4 base and stress net means remain
negative in all six split cells; non-circular synchronized 7-calendar-day
intervals remain below zero. Excluding funding at the exit boundary changes
base means only slightly and leaves them negative in all six cells. Coverage
is 99.994–100%; market-wide non-overlap counts range from 1,271 to 16,998 and
are not independent observations. The four-role second-round panel concluded:
Blue allows only a distinctly preregistered, future-only asymmetric mechanism
test (not another seesaw tuning pass); Red accepts the bootstrap correction but
flags funding boundary ambiguity; Methods confirms this is only a pre-M2
exploratory rejection; Judge rejects progression to M2. M2 was not measured
because neither source defines a stop/target barrier for this rule. Decision:
reject this simple proxy before M2 design; do not generalize that decision to
every cross-asset model or to the paper results. All history was previously
exposed, and fee proxies omit spread/slippage.

- Frozen rule: `inventory/PREREG_CROSS_ASSET_SEESAW_SCREEN_20261120.md`.
- Canonical corrected run: `inventory/runs/cross_asset_seesaw_screen_20261120_v4/`.
- v2, v3, and the initial output are retained as superseded intermediate artifacts.
- v4 uses complete split-specific anchor grids with zero returns at no-signal
  times, reports opportunity coverage and market-wide non-overlap counts, uses
  non-circular 7-day moving blocks, and exposes funding endpoint sensitivity.
- Final four-role vote on v4: 4/4 reject progression of this proxy to M2; all
  reviewers limit the finding to the fixed rule, not the broader mechanism.
- Blue team's only distinct follow-up lead is an asymmetric “positive leader
  shock / large-vs-small next-hour relative return” mechanism test. It is not
  yet preregistered or tested. Since all available periods have already been
  exposed, any confirmatory version must use genuinely new forward data; it is
  only a mechanism screen and cannot itself pass the M2 trading gate.
- Sources: [Jia et al. (2023)](https://doi.org/10.1016/j.jempfin.2023.101428),
  [Guo et al. (2024)](https://www.sciencedirect.com/science/article/pii/S0165188924000551).

Date: 2026-11-20
Scope: public SNS, TradingView indicators, public trading communities, and GitHub/agent skills. Historical research only; no orders, deployment, or live signals.

## Decision

No candidate from the four source groups is ready for a strategy-performance backtest, and no validated core was found. The OI archive lead is now eligible for a full data-quality audit, not for signal scoring. Phase 9 remains blocked because there are zero individually validated core strategies.

The fixed crypto gate remains unchanged: target-first M2 at least 80%; total issued signals and a separate non-overlap sample of at least 200; at least 20 symbols; at least 10% coverage; positive net expectancy after both base and stress costs; the 95% Wilson lower bound above the valid frozen baseline; M1 direction accuracy reported separately. Existing historical sealed intervals have already been exposed and cannot be presented as untouched OOS.

## Repository baseline reviewed

- `docs/chart_predictor/SPEC.md` and `docs/chart_predictor/REFERENCES.md` define the signal and causal evaluation contract.
- `docs/research/binance-um-metrics-snapshot-audit-2026-11-19.md` already found symbol/date-dependent timestamp defects in Binance metrics, including AERGOUSDT off-grid seconds and conflicting duplicated day-boundary rows; it ruled the dataset ineligible as a strategy feature pending broader provenance/availability work.
- `docs/research/inventory/plan_execution_status_20261120.md` records 38 existing hourly setups × 2 horizons: 0/76 reached M2 80%; the best reported sealed cell was 38.46% with N=26. The sealed interval was previously exposed.
- The funding-tail reversal candidate is already rejected. Existing setup families include Donchian/breakouts, RSI divergence, Fibonacci pocket, sweep/CHoCH, order blocks, VWAP, volume climax, Heikin-Ashi and others.
- The current USD-M archive used by the common study is hourly and covers 36 symbols. It does not by itself provide 5-minute OI or liquidation histories.

## Four-source scouting

| Source group | Research leads | Evidence and overlap | Disposition |
|---|---|---|---|
| SNS / public videos | Stop-hunt followed by OI contraction; CVD divergence/absorption | The public descriptions omit quantitative sweep/OI/CVD rules, entry, stop, target and expiry. OI needs timestamped metrics; CVD needs direction-classified trades. The reported funding+OI lead duplicates the rejected funding-tail family. | OI: data audit only. CVD: defer pending bounded data-size and schema audit. No strategy backtest. |
| TradingView / Pine | Strategy 432 BTC Donchian Breakout Continuation; another Donchian breakout variant | Strategy 432 describes previous-channel close breakout plus ATR breakout filter, ADX and EMA200; exits use opposite Donchian break or fixed bars. Exact input defaults and thresholds are absent from the page. Existing Donchian research makes this a likely filter variant, not a new family. | Exclude from new-candidate queue until full source/defaults exist; even then, require an explicit incremental-value hypothesis against existing Donchian tests. |
| Public community | OI/funding/order-book volatility filter; market-wide liquidation rebound | One post reports absolute-move predictability, not directional entry edge; parameters, exits, costs and raw data are absent. Liquidation rebound is vague and overlaps sweep/reversal research. Both are author reports, not independent evidence. | No candidate eligible for scoring. Liquidation data remain a separate missing input. |
| GitHub / skills | Momentum-breakout postmortem; crypto-strategy-backtest; crypto-trader-skill | HodlHook reports all locked variants lost on its holdout (-0.13R to -0.33R) and warns of survivorship bias; this is negative, externally reported evidence and overlaps breakout studies. xy3293 is a framework with Turtle/Keltner examples, not a novel edge. crypto-trader-skill is workflow tooling, not a strategy. | Do not add a strategy based on tool/agent existence. Treat external results as unverified until independently reproduced. |

Sources:

- [TradingView Strategy 432](https://www.tradingview.com/script/tuC7aGNI/)
- [HodlHook momentum-breakout postmortem](https://github.com/HodlHook/momentum-breakout-postmortem)
- [Public OI/volume/funding magnitude study](https://www.reddit.com/r/algotradingcrypto/comments/1xhg9v3/i_tested_whether_volume_open_interest_and_funding/)
- [Public liquidation/strategy-search post](https://www.reddit.com/r/Daytrading/comments/1xx3xkr/i_backtested_400000_crypto_strategies_on_6_years/)
- [Binance public-data repository](https://github.com/binance/binance-public-data)
- [Binance Vision Dataset Terms](https://github.com/binance/binance-public-data/blob/master/TERMS_AND_CONDITIONS.md)
- [Binance public-data Issue #491: metrics timestamp concerns](https://github.com/binance/binance-public-data/issues/491)

The two YouTube leads (OI contraction after a stop hunt; CVD divergence/absorption) came from public video descriptions. The descriptions did not provide complete reproducible entry/exit rules. No quotation or script code was copied.

## Four-agent review and debate

The four research agents were reassigned as Blue Team, Red Team, independent methods reviewer, and judge. They reviewed the initial scouting results, then reconsidered the data claim after the public metrics path was found, and issued a final disposition after local sample checks.

- **Blue Team:** OI contraction after a stop-hunt is structurally distinct from channel breakout, but the source hypothesis is qualitative and requires OI/liquidation data. Price-only testing cannot validate it.
- **Red Team:** Donchian candidates duplicate tested breakout families and lack exact defaults; the other proposed sources lack complete rules or historical inputs.
- **Independent reviewer:** none of the source candidates has evidence meeting the frozen M2, N, symbol, coverage, cost, and baseline gates. Historical sealed rows cannot be reused as untouched validation.
- **Judge:** allow a bounded OI data-quality audit only. Keep strategy scoring and Phase 9 blocked. If a new strategy is designed after the audit, label it as a new, independently preregistered hypothesis rather than a reproduction of the source video.
- **Final four-agent vote after direct timestamp reconstruction:** all four agreed that the taker ratio's forward five-minute bucket may not be used at its label timestamp, this observation cannot be generalized to OI fields, the full OI archive and OI-specific timing still need audit, and no performance score or Phase 9 move is allowed yet.

The agents agreed that the OI hypothesis has not passed the data gate, has no fixed trading rules, and has no performance evidence. Their agreement is not itself quantitative evidence of profitability.

## OI metrics sample audit (read-only market data)

### Checks performed

1. HTTP HEAD checks on the fixed 36-symbol USD-M cohort for daily `metrics` ZIPs at `2023-03-24` and `2026-05-31`: **72/72 returned HTTP 200**. These are endpoint-existence samples only; they do not prove the intervening days exist or are valid.
2. Downloaded one BTCUSDT daily metrics ZIP to `/private/tmp/cointrade-metrics-BTCUSDT-2025-01-01.zip` with its `.CHECKSUM`. The file SHA-256 was `cfabcf9c533d40d0832141340f7e5c9d678f614cf502c3cbe2623eebed4cef03`, matching the publisher checksum. ZIP contained one CSV with 288 five-minute rows plus header, and columns for `sum_open_interest`, `sum_open_interest_value`, long/short ratios, and taker long/short volume ratio. That day's labels ran 00:00 through 23:55 UTC with no within-file duplicate or off-grid timestamps.
3. Downloaded BTCUSDT metrics ZIPs for `2026-06-24` and `2026-06-25`; both publisher checksums passed and both currently served samples contained 288 rows labeled 00:00 through 23:55 UTC.
4. A paginated public S3 object listing for the fixed 36-symbol cohort and `2023-03-23`–`2026-05-31` found **41,967 of 41,976** expected daily ZIPs. Nine ZIPs and their corresponding `.CHECKSUM` objects were absent: ICPUSDT `2023-11-07`, `2023-12-16`; NEARUSDT `2023-12-18`; STXUSDT `2023-12-08`; THETAUSDT `2023-12-08`; XLMUSDT `2023-12-13`; XMRUSDT `2023-12-17`, `2023-12-18`; ZECUSDT `2023-12-13`. Listed ZIP payload sizes total `483,391,413` bytes (about 461 MiB), excluding checksum files. This is metadata inventory only; those ZIPs were not all downloaded or validated.
5. Downloaded checksum-verified BTCUSDT `aggTrades` files for `2025-01-01` and `2026-06-23`–`2026-06-25` (about 85 MB combined in the local temp directory). Reconstructed 5-minute taker buy/sell base-volume ratio from `quantity` and `is_buyer_maker`, then compared it to `sum_taker_long_short_vol_ratio`:

   | Date | Same-label `[T,T+5m)` correlation | Prior-window `[T-5m,T)` correlation | Matched rows |
   |---|---:|---:|---:|
   | 2025-01-01 | 0.999962 | 0.124142 | 288 |
   | 2026-06-23 | 0.999750 | 0.124241 | 288 |
   | 2026-06-24 | 0.999703 | 0.145552 | 288 |
   | 2026-06-25 | 0.999380 | 0.042792 | 288 |

   Mean absolute log-ratio error on the same-label mapping was 0.002222 on 2025-01-01 and 0.002775, 0.002523, 0.002220 on June 23–25, respectively. The reconstruction matches the future 5-minute bucket beginning at `create_time=T`, not the preceding bucket. Using this ratio as if it were known at T would leak up to five minutes of future flow. A historical signal must not consume it before the associated interval ends; exact real-time publication latency remains unmeasured.

6. A HEAD request for BTCUSDT `aggTrades` on `2025-01-01` returned HTTP 200 and a content length of 9,357,158 bytes. The downloaded file checksum passed. This indicates that broad trade-level CVD research could have a materially larger data footprint than sampling compact five-minute metrics.

The local object inventory is `/private/tmp/cointrade-oi-archive-inventory.json`. Sample ZIPs and publisher checksum files are under `/private/tmp/cointrade-metrics-*`, `/private/tmp/cointrade-metrics-boundary`, and `/private/tmp/cointrade-aggtrades-timing`. These are temporary audit inputs, not full historical datasets or strategy result files.

### Limitations and discrepancy

- The 72 endpoint checks and four BTC metrics files are sparse samples, not a full archive audit. The public S3 inventory found only nine missing daily objects in the stated period, but ZIP checksum, schema and row integrity have not been checked for the remaining 41,967 files.
- The earlier cross-symbol audit in `docs/research/binance-um-metrics-snapshot-audit-2026-11-19.md` has already demonstrated that a global timestamp shift or naïve deduplication is unsafe. Therefore, the archive-listing result does not make OI eligible: the symbol/date-specific timestamp and duplicate-row defects must be understood before any feature construction.
- The currently served 2026-06-23/24/25 samples, plus 2025-01-01, show the same start-labeled forward-bucket behavior for the taker ratio. That does **not** reproduce Issue #491's exact assertion that June 24 was end-labeled and June 25 start-labeled. The reason for the discrepancy is unknown. HTTP `Last-Modified` for the sampled files is July 24, 2026 (2025-01-01) and July 29, 2026 (2026-06-24), before the issue's reported August publication; do not assume a post-issue correction explains it. Keep the issue unresolved and do not extend taker-ratio timing results to OI fields.
- The verified taker-ratio mapping establishes a causal alignment warning for that field only. It does not establish OI snapshot time, metric publication latency, or full-series integrity.
- The 2025 sample is not enough to prove that OI values were available at the labeled timestamp. A field can be a snapshot or a period aggregate, and those have different causal alignment.
- Binance's official public-data terms restrict these datasets to permitted non-commercial uses such as personal, non-production historical backtesting; they do not authorize live execution or third-party signal distribution. The current Binance REST OI-history endpoint is limited to recent history, so a long historical study would rely on archives whose exact coverage must be audited.
- No strategy outcomes were calculated, no performance test was run, and no benchmark was scored in this phase.

## Research sequence and gates

1. **Eligibility decision before bulk validation.** Treat metrics as ineligible now. The 41,967-object listing is not a request to download 461 MiB blindly. First define a stratified, reproducible validation sample covering symbols, years, reported defect classes, adjacent date boundaries, and checksum/schema anomalies. Expand to the full cohort only if the sample identifies a plausible, deterministic repair that preserves point-in-time validity.
2. **Structural/time audit.** For any authorized research sample, check ZIP integrity, CSV schema, row counts, nulls, duplicate/off-grid timestamps, daily-boundary conflicts and symbol/date alignment. Preserve original files and checksum manifests. Never globally shift timestamps or drop duplicates without field-level evidence.
3. **Field availability audit.** Establish whether each field is a point-in-time snapshot or interval aggregate and when it could first be known. The taker-ratio reconstruction shows forward-bucket semantics only for that field in sampled files; it does not validate OI timestamps. If historical OI timing cannot be established, stop this candidate before signal testing.
4. **Rule gate.** The source's OI-stop-hunt mechanism still lacks exact sweep definition, OI change window/threshold, signal confirmation, entry, stop, target, expiry and same-bar execution treatment. Do not invent these and call it the source strategy. After the data gate, any designed variant must be labeled a new hypothesis and frozen in a preregistration before viewing its outcomes.
5. **Exploratory screening only.** Because previously tested historical candle intervals are exposed, retrospective results may be used to debug and reject but cannot establish a sealed pass. Report every trial, compare to frozen baselines, add funding and both cost scenarios, and use causal prefix/future-mutation tests.
6. **Forward paper evaluation.** Any promising, preregistered candidate must be evaluated on future, append-only paper signals until the fixed total and non-overlap sample gates can be assessed. No real order placement is in scope.
7. **Robustness and Phase 9.** Only candidates that independently pass the frozen gates proceed to walk-forward/untouched forward verification, parameter neighborhood, cost stress, Monte Carlo/block bootstrap, multiple-testing adjustment, and independent ledger review. Phase 9 portfolio mixing remains prohibited until at least one strategy is validated as a core.

## Worktree and preservation note

The active research checkout is `/Users/user/Desktop/CODE/trading_bot`, branch `research/bat-harmonic-validation-20261120`, initially based on commit `489c538697061c3ed2961d790735d3a8a16473fd`. The canonical `main` worktree was not edited. At initial inspection, the tracked 256 MB Git LFS ledger appeared modified and default `git status` failed because the shared LFS clean filter could not write under the canonical repository's `.git/lfs/tmp`; the ledger was never staged. After committing this report, a fresh status check completed successfully and showed the branch clean. The report is committed as `4e21813f0b9ff6b38d80dfafebf8e03fd842ae7b`; `git ls-remote` confirmed that exact hash at `origin/research/bat-harmonic-validation-20261120`.

The downloaded sample files, object-listing manifest and checksums are in `/private/tmp`; they are not repository artifacts and are not referenced as complete research data. The 483 MB listed ZIP payload remains undownloaded. No tracked strategy code or historical run was changed.

## Second four-source review and cross-panel decision (2026-11-20)

Four independent source scouts reviewed public SNS/video, TradingView/Pine, public communities, and GitHub strategy/skill repositories. They read the crypto SPEC and the relevant strategy registry/research notes before proposing leads. The scouts did not install code, run performance tests, access accounts, post comments, or change files. Their results were then sent as one fixed candidate pool to separate Blue, Red, Methods, and Judge reviewers.

### Source-scout outcome

| Source group | Candidate lead | Duplicate / evidence decision |
|---|---|---|
| SNS / public posts | Funding timing, cross-exchange carry, funding+OI, liquidation flush | No new complete strategy. Funding/carry overlaps existing funding families; liquidation flush overlaps sweep/reversal. Posts do not establish independent performance. |
| TradingView / Pine | CVD divergence with confirmed price-turn; OI shock followed by event-range breakout | CVD is a candidate signal family but overlaps price divergence/reversal and needs executable barriers. OI shock is potentially distinct only if point-in-time OI is valid; rule and exits are incomplete. Public script logic is not a license to copy code. |
| Public communities | Liquidation burst rebound; volatility-only entry/risk gate | Liquidation rebound overlaps sweep/reversal and needs genuine timestamped liquidation observations. Volatility-only gating is risk management, not a standalone directional strategy. Anecdotal posts are not performance evidence. |
| GitHub | Liquidation-pressure maker-entry filter; BTC→SOL momentum; liquidation-tail rebound | Maker filter is an execution hypothesis, not a complete strategy, and requires L2 queue/fill evidence. BTC→SOL overlaps the already tested cross-asset lead-lag family. Tail rebound overlaps existing sweep/reversal. Frameworks and skills were not counted as strategies. |

### Cross-panel vote

| Reviewer | Decision |
|---|---|
| Blue | OI shock followed by event-range breakout is the strongest mechanism to investigate, but only through a bounded data-availability/integrity audit. It is not yet a preregistered strategy and may reduce to an OI filter on an existing breakout family. |
| Red | No candidate may progress to sealed-OOS scoring. Historical intervals are already exposed; OI timestamp availability is unresolved; liquidation-side observations and maker-queue fills are unavailable; the five labels collapse to reversal, derivatives-pressure, and risk-gating families. |
| Methods | The 2025 four-date sample can smoke-test CVD aggregation and timestamp handling only. It cannot establish regime robustness or performance. OI, liquidation, and L2 candidates need their actual input data and availability timestamps before signal construction. |
| Judge | **0/5 candidates approved for standalone strategy scoring.** Proceed only with OI data-quality/point-in-time audit. Keep Phase 9 blocked. |

The outcome is a research eligibility decision, not evidence that these mechanisms cannot work. The fixed success gates remain unchanged. No strategy return, M2, baseline, or benchmark score was computed in this review.

### Local trade-archive sufficiency check

Read-only inspection found 80 ZIP files under `/private/tmp/binance-aggtrades-multiday-2025`: 20 symbols each for `2025-01-01`, `2025-04-01`, `2025-07-01`, and `2025-10-01`, split evenly between `aggTrades` and `1m` klines. Directory size was 325 MiB. This sparse sample contains four isolated days, not a continuous time series or broad set of market regimes. ZIP/checksum integrity was not re-audited in this check. It is therefore not eligible for strategy-performance scoring; at most it can support a separately preregistered aggregation/timestamp pipeline smoke test. No such smoke test was run.

### Next research order

1. **OI archive eligibility audit only:** choose a small stratified sample covering symbols, years, known defect classes, adjacent daily boundaries, and available checksums. Preserve raw files and record source, file hash, schema, field units, label time, publication/availability evidence, gaps, duplicates, and cross-day conflicts. Do not infer that a label timestamp is the availability time.
2. **Stop/go on the OI input:** if historical point-in-time availability cannot be established, reject OI-based historical scoring. Do not substitute a price/OI-derived liquidation proxy for actual liquidation flow.
3. **Only after data eligibility, decide whether to preregister one fixed OI-event hypothesis.** Freeze the OI shock definition, completed-bar event range, confirmation deadline, next-executable entry, stop, target, expiry, same-bar tie handling, funding, costs, and the price-only breakout control before accessing candidate outcomes. Label historical results exploratory because previously viewed windows are not sealed OOS.
4. **Forward validation:** only an eligible, fully specified candidate can be put into append-only paper-signal evaluation on genuinely future data. No real orders or Oracle deployment are included.
5. **Phase 7 robustness, then Phase 9:** only an individual candidate passing the frozen M2/sample/coverage/cost/baseline gates can proceed to robustness and eventually portfolio combination. No candidate currently meets that condition.

### Reproducibility and limits

- The four source-scout reports and four cross-review reports are preserved in the current Codex task messages; this document records their joint determinations and the basis for the next gate.
- The check used the current checkout at `/Users/user/Desktop/CODE/trading_bot`; current branch at audit time: `research/bat-harmonic-validation-20261120`, HEAD `f3dcf764e91cefc49aad94d0c111d31cfe21e9a0`, working tree clean before this documentation change.
- The local ZIP inventory command counted filenames and read ZIP member metadata; it did not extract or checksum all 80 files. The NAS volume was not mounted in this environment, so NAS-resident data was not inspected.
- Public-source investigation was limited to the four scouts' searches and the cited repository/source pages. It does not establish that no novel strategy exists anywhere.
