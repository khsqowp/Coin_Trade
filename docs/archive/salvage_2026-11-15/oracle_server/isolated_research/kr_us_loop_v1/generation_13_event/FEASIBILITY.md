# Generation 13 event-driven candidate feasibility — PEAD

Date: 2026-11-06 (Asia/Seoul)  
Status: **data-blocked; no market-price values, signals, or performance statistics were read or computed.**  
Scope: read-only inspection of the local research mirror, schemas, filenames, and prior research notes. No Oracle/server access, live trading, commit, or push.

## Finding

Post-earnings-announcement drift (PEAD) is materially different from the tested daily-bar trend, momentum, reversal, sector-rotation, volatility, and fixed-schedule rules. The local files do **not** contain the event-time and point-in-time earnings inputs needed to construct a defensible PEAD test. A conceptual hypothesis can be described, but a complete candidate cannot be preregistered without fabricating or silently substituting key data.

This is a local-data limitation, not evidence that PEAD has no edge. No return evidence was generated in this task.

## What the local inventory actually contains

The audit inspected filenames and schemas/field names only; it did not load OHLC/price or return values.

| Local source | Observed fields/schema | Relevance to PEAD |
|---|---|---|
| `data_mirror/us_daily/*.events.json` (737 files) | Top-level `dividends` and `splits`; populated event entries are positional pairs of string and numeric values. | Corporate-action events only. No earnings event type, announcement timestamp, EPS actual, fiscal-period ID, estimate, or revision history. The positional pair semantics are not sufficient to treat this as earnings data. |
| `data_mirror/us_daily/*.meta.json` (737 files) | `symbol`, `source`, `url`, `fetched_at`, `sha256`, `rows`, `first`, `last`, and vendor metadata keys `currency`, `exchangeName`, `firstTradeDate`, `instrumentType`, `longName`, `shortName`. The source ID is `yahoo chart v8 (unofficial, key-less)`. | Price-file provenance metadata; no financial statement or earnings-event provenance. |
| US PIT membership file `data_mirror/us_daily/pit/sp500_ticker_start_end.csv` | `ticker`, `start_date`, `end_date`. | Membership spells only. No permanent security ID, earnings events, or accounting data. |
| Daily price parquet schemas | `open`, `high`, `low`, `close`, `adjclose`, `volume`, `date`. | Daily bars cannot establish when earnings became public or what the market could know before release. |
| `data_mirror/kr_daily_v2/universe/universe_raw.csv` and market HTML snapshots | Security/universe listing materials; no financial-statement or earnings-event datasets were found by filename/schema inventory. | Not an earnings source. Current/universe snapshots cannot replace event-time accounting history. |
| Existing local research notes and source mirror | Prior feasibility notes explicitly say PIT statements, surprises, consensus, and announcement timestamps are absent. No local filenames matching earnings/EPS/consensus/estimate/filing fundamentals were found in the research tree. | Confirms the blocker is already known; this audit found no local data that resolves it. |

The event JSON format and vendor label establish only what this local feed claims to contain. They do not establish completeness, historical corrections, source authority, or point-in-time availability.

## Minimum data contract for a fixed PEAD candidate

One instrument-level event table must be available for the full eligible active-and-delisted universe, not only current survivors. Each row must be keyed by a permanent security identifier and contain:

1. **Identity and coverage**
   - `security_id` (stable issuer/security identifier), `ticker`, `ticker_valid_from`, `ticker_valid_to`, `exchange`, `country`.
   - `universe_member_from`, `universe_member_to`, and the frozen point-in-time universe source/version.
   - Explicit security delisting/merger status and delisting return or a link to the corresponding total-return price series.
2. **Earnings observation**
   - `fiscal_period_id` (fiscal year, quarter, period end, and period type), `currency`, `accounting_standard`, and a stable EPS definition (basic/diluted; continuing operations vs reported total).
   - `actual_eps`, `actual_eps_originally_reported`, `actual_eps_revision_timestamp`, and source filing/release ID. Restatements must be represented as versions rather than overwriting the original value.
   - The prior comparable EPS observations needed for a frozen surprise denominator, or a source-supplied surprise with its own formula/version. A non-consensus SUE rule still needs the full, point-in-time trailing EPS history used in its scaling denominator.
3. **Public availability and execution mapping**
   - `public_release_timestamp` with timezone and source; `filing_accepted_timestamp`/`disseminated_timestamp` where available; `timestamp_precision` and a documented rule for after-hours, weekends, exchange holidays, and ambiguous/date-only records.
   - `first_executable_session` derived mechanically from the public timestamp and the frozen market calendar, never inferred from the daily price response.
4. **Source lineage and missingness**
   - `source_id`, `source_record_id` (e.g. filing accession/receipt number), `retrieved_at`, `source_version`, raw-record hash, correction/cancellation status, and an explicit distinction among `no event`, `not covered`, and `missing/invalid`.

For **consensus-based SUE**, add a separate estimate snapshot table with `security_id`, `fiscal_period_id`, `estimate_value`, estimate definition/currency, `estimate_timestamp`, `analyst_or_consensus_source_id`, snapshot/record ID, and revision history. Select the last estimate genuinely available strictly before the release timestamp. A later-restated consensus value is not an acceptable substitute.

## Source IDs to acquire or validate

No authoritative earnings data source is currently present in this local mirror. A future acquisition should identify, license, version, and hash one source per market before preregistration. Candidate source identifiers to evaluate—not claims of current local availability—are:

- **US filings/release records:** SEC EDGAR filing accession number (`accession_number`) plus issuer CIK and filing acceptance/dissemination timestamp; for earnings-release events, preserve the actual release/exhibit record and its public timestamp. SEC filing acceptance alone may be later than the original release and must not be represented as the release time without evidence.
- **KR filings/release records:** DART `corp_code`, `rcept_no`, and `rcept_dt`/disclosure receipt metadata, with the original filing/document and the finest authoritative public timestamp available. A date-only receipt field is not sufficient to decide whether same-day market execution was possible.
- **Actual EPS:** source record ID, fiscal period, EPS measure/definition, originally published value, currency, and version/correction history. SEC XBRL/DART accounting facts can support actual reported values only when linked to the exact accepted filing and its availability time; a current facts endpoint alone is not PIT history.
- **Consensus (optional variant):** a licensed historical analyst-estimate snapshot vendor with timestamped pre-release consensus revisions, stable security mapping, and restatement/version history. The local mirror has no such feed.
- **Market/universe linkage:** permanent-ID mapping through time, delisting-inclusive PIT membership, historical exchange calendars, split/dividend-adjusted total returns, and delisting proceeds/returns. Existing ticker-only membership and unofficial Yahoo-derived daily snapshots do not satisfy this contract.

These names describe the identifiers and evidence a source must supply. No external API was queried or validated for this report, and no source is claimed to be licensed or available in the workspace.

## Can a candidate be frozen now?

**No—not as a testable strategy with an auditable information set.** A conceptual rule could be written as “after a positive standardized quarterly EPS surprise, enter at the first executable session and hold a predeclared fixed horizon,” but doing so now would leave the following critical choices/data unresolved:

- Which precise EPS definition and fiscal-period matching rule?
- Surprise versus what: a historical seasonal EPS model or analyst consensus? The latter requires PIT estimates.
- What is the exact public release time, and which session is the first tradable one?
- How are ticker changes, delistings, corrections, missing earnings history, overlapping releases, and transaction costs handled?
- Which source/version and pristine evaluation period are frozen?

Choosing these from observed outcomes or filling them with current/revised data would introduce avoidable hindsight and measurement bias. The next valid step is **data acquisition/lineage validation only**, followed by a new preregistration after the event schema and coverage gates pass. If no PIT feed can be sourced, PEAD remains explicitly data-blocked; it must not be replaced with price-gap proxies and labeled PEAD.

## Validation checklist before a future preregistration

- [ ] Full active-and-delisted security coverage reconciled to the frozen US/KR PIT universes.
- [ ] Permanent identifier and ticker-history joins validated, including corporate actions and delisting outcomes.
- [ ] Original earnings facts and all revision/correction timestamps retained.
- [ ] Public announcement timestamps, timezone, precision, and source record IDs present; date-only ambiguity handled by a frozen conservative execution rule.
- [ ] Consensus snapshots and pre-release timestamps present if the consensus SUE variant is selected.
- [ ] Explicit no-event vs uncovered vs missing records distinguishable and coverage thresholds fixed before returns are read.
- [ ] Candidate formula, execution, holding horizon, cost model, benchmark, untouched evaluation interval, and cumulative multiple-testing count frozen before any performance calculation.

## Scope check

- No price field values, signals, strategy returns, or performance statistics were inspected or computed.
- No remote host was accessed; no production process, live order, git commit, or push was touched.
- This report documents data feasibility only and does not conclude that PEAD or event-driven trading is unprofitable.
