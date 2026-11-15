# Round 5 readiness audit and prospective crypto MTF protocol

Date: 2026-11-15 (Asia/Seoul)
Status: readiness audit complete; no performance backtest run in this round.

## Executive disposition

Four independent read-only audits were completed: KR equities, US equities, crypto signal evidence, and crypto multi-timeframe coverage. None produced a new performance result. The equity tests were blocked by provenance/universe/data gates; the crypto post-development rows were not proven sealed. No 80% accuracy claim is supported, and no trading or deployment action was taken.

| Workstream | Verified finding | Disposition |
|---|---|---|
| KR stocks/ETFs | Local cache has 92 named CSVs. Existing records cover momentum, reversal/panic reversal, calendar, low-risk/low-skew, and volatility-breakout families; the cache's price rights, adjustment/vintage, PIT membership, actions, and delisting outcomes remain unresolved. | No valid fresh price-only performance test is currently eligible. Do not substitute tickers or reuse the already-viewed cohort as independent evidence. |
| US stocks/ETFs | Local cache has 92 named CSVs; `US_AGG.csv` is absent. Several files have unequal history. Existing candidates are already recorded; current-cohort/PIT and corporate-action provenance remain unresolved. | The AGG-dependent candidate is blocked. No proxy substitution or new performance sweep. |
| Crypto single-TF signals | P5–P8 cover trend/SMC, volatility squeeze, session breakout, mean reversion, and volume exhaustion. Their registered Stage C gate was 75% target-first hit rate and at least 30 events per cell, not the user's 80% target. No passing cell is documented. | Existing results are development evidence only; they do not prove 80% precision. |
| Crypto MTF | P5–P8 include a closed-HTF SuperTrend direction filter, but no documented cross-timeframe signal consensus or per-timeframe asynchronous target deadlines. | A distinct hypothesis is eligible for preregistration, not for a claimed performance result on the currently unsealed rows. |

## Evidence boundary

The local `vision_dev.sqlite` metadata reports 19,776,458 rows across six symbols from 2020-01-01 through 2026-06-30. The local `candles.sqlite` metadata reports 17,142,161 rows across 100 symbols, with open timestamps from 2026-07-17 through 2026-11-14; the separate read-only metadata audit reported 5,149,756 rows after the P5–P8 development cutoff at 2026-10-09T00:00:00Z. The latter database is not accompanied by `chart_predictor/data/sealed_registry.json`, and an access history proving those later rows were never inspected for performance is unavailable. Presence after a cutoff is not proof of a sealed holdout. This audit did not read post-cutoff OHLCV or labels.

The KR and US reports describe metadata-level cache inventories only. The KR audit did not read price values. The US audit found `US_AGG.csv` missing and did not calculate performance. These inventories do not establish a point-in-time investable universe or validate data use rights.

## Proposed hypothesis for the next eligible crypto trial (preregister before data access)

This is a proposed new test of cross-timeframe agreement, not an asserted edge. It must not be run against any validation/sealed prices until the input freeze and access log are established.

### Objective and labels

At each eligible closed-bar signal, create a directional forecast with a next-bar-open entry, structure-derived stop, and 2R target. Evaluate target-first outcome at separate checkpoints of 10 and 20 timeframe bars. The final deadline is 20 bars. If stop and target are both touched within the same underlying 1-minute candle, count the stop first. If neither barrier is touched by the deadline, record timeout as a non-hit for target-first precision and report it separately. Long and short are symmetric. Use the currently frozen SPEC §14.1 fee of 0.10% round trip; do not add slippage, depth, or fillability variables in this test. Report 4x/5x outcomes separately with the existing approximate liquidation formula and its fixed 0.5% maintenance buffer; flag stop levels beyond that estimate. It is not a symbol/position-tier exchange liquidation quote and does not replace account-specific risk checks.

### Candidate signal and agreement rule

Use only the four already-coded, mechanism-distinct base rules: `bb_squeeze_breakout`, `orb_funding_session`, `vwap_band_fade`, and `volume_climax_exhaustion`. Do not tune their internal thresholds. Evaluate 1m, 3m, 5m, 10m, 15m, 30m, 60m, 120m, and 240m bars, all aggregated causally from complete 1m candles. The signal bar must be fully closed; the entry is the next bar open. At each symbol and decision time, a timeframe contributes at most one vote: its most recent eligible base-rule signal, no older than one bar of that timeframe, and whose next-bar entry is not already through its stop or target. A forecast is emitted only when at least two distinct timeframes vote for the same direction. Conflicting or stale votes produce abstention. Each contributing timeframe retains its own stop, target, 10-bar checkpoint, and 20-bar deadline; forecasts sharing a consensus decision are clustered as one event for uncertainty calculations, not counted as independent events.

### Sampling and statistical gate

Freeze the symbol universe prospectively at the first collection timestamp; document listing/delisting handling and preserve every symbol's eligibility history. Do not select symbols by future volume rank. Suppress overlapping events per symbol and timeframe until that timeframe's 20-bar deadline; additionally report dependence-clustered uncertainty by consensus event, symbol, and UTC day. Record coverage as emitted eligible forecasts divided by all eligible decision times, both overall and per timeframe. Compare target-first precision against same-timeframe momentum continuation, a fixed-seed random direction baseline, and flat/abstain baseline under identical horizons and costs.

For every timeframe and direction reported as a pass, require at least 80% point precision, at least 10% coverage, N≥200 non-overlapping forecasts across at least 20 symbols, Wilson 95% lower bound above all registered baselines, positive mean net R after costs, and no single symbol contributing more than 20% of qualifying forecasts. Report per-timeframe and per-side breakdowns. A failure of any gate is `NOT_PASSED`; insufficient sample is `INCONCLUSIVE`, not success. Freeze thresholds and rules before the final holdout is opened. Score the final holdout once; any post-result change consumes that holdout and requires a new prospective cohort.

### Required before execution

1. Resolve the precise execution of event aggregation, vote freshness, tie handling, and same-bar barrier semantics in a unit-tested deterministic scorer.
2. Create an immutable manifest with code SHA, rule text, timeframe widths, symbol cohort, data-source schema, start/freeze timestamp, and trial registry entry.
3. Establish an append-only sealed-data boundary and access log independent of the scoring process. Do not designate the existing post-2026-10-09 rows as sealed retroactively without evidence.
4. Collect genuinely future data after the protocol freeze. If there is not enough eligible sample, continue collection without examining aggregate performance.

## Equity next gates

- **KR:** For a price-based strategy gate, first obtain a permitted, versioned price/corporate-action dataset with point-in-time security universe and delisting outcomes. Separately, disclosure families (ownership changes, short balance, buyback progress, as-filed earnings drift) remain feasibility leads; each needs publication timestamps, revisions, historical issuer/security mapping, rights, and an independent price panel before preregistration.
- **US:** Do not rerun or alter the AGG-dependent fixed universe until the exact required history is available from an admissible source. Do not shrink the universe or substitute a bond ETF. Existing local CSVs cannot establish PIT constituents, delisted outcomes, or adjusted-price provenance.
- For both markets, resolve the SPEC's still-open benchmark, tax/cost model, universe, position sizing, and maximum drawdown policy before any strategy can be called validated or deployment-ready.

## Audit provenance and limitations

The four individual read-only reports were produced under `/private/tmp/round5_kr/REPORT.md`, `/private/tmp/round5_us_agent/REPORT.md`, `/private/tmp/round5_crypto_audit/REPORT.md`, and `/private/tmp/round5_crypto_mtf/REPORT.md`. They are task-local temporary evidence, not repository inputs. This consolidated note independently checked the local repo HEAD, clean status, database table schemas/metadata, equity CSV counts, and required `US_AGG.csv` absence. It did not reproduce prior performance calculations, validate every candle gap, or establish the external data licenses. No new performance trial was run; the trial count is unchanged.
