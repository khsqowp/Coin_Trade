# Gen12 Macro Overlay — Read-Only Feasibility Audit

Date: 2026-11-07 (Asia/Seoul)  
Candidate: `GEN12-US-FED-TIGHTENING-12M-SPY-CASH-1X`  
Scope: preregistration, data-source feasibility, implementation readiness, overlap, and benchmark inputs only. No SPY price values, signals, returns, or performance statistics were accessed or computed. No remote host was accessed and no existing generation artifact was edited.

## Decision

**NO-GO for any performance run now. Conditional GO is feasible after a frozen event table, verified session mapping, and benchmark provenance/data gates pass.** The Fed has authoritative, freely accessible primary sources for meeting decisions and announced rate levels. The current local files do not contain the required event table, and the existing SPY file is identified as an unofficial Yahoo chart feed, not an authoritative or licensed price/calendar snapshot. The policy-source gap is therefore addressable; the benchmark/data-quality gap is not resolved by PyArrow or by public Fed data.

This is a feasibility finding, not a strategy rejection.

## Evidence inspected

- `generation_12_macro/PREREG.md`, `STATUS.md`, and `FREEZE.md`: rule is fixed and hash-frozen, but explicitly pending independent review and root GO; no event table or runner is present.
- Existing local SPY metadata: `SPY.parquet` has 8,498 rows with date span 1993-01-29 through 2026-11-02. Its sidecar says source `yahoo chart v8 (unofficial, key-less)`, fetched 2026-11-03, and includes a content hash. Only schema/date metadata were read; no price values were read.
- Existing US PIT membership inventory: 1,262 membership intervals across 1,209 tickers, earliest membership interval 1996-01-02. It is not needed for a SPY-only strategy’s holdings, but confirms the project’s broader US PIT universe does not make SPY source provenance authoritative.
- No frozen FOMC event table was found in the Gen12 macro directory.
- Prior catalog: `FEASIBILITY.md` records a crypto-derived FOMC time-window exposure overlay. Gen12 is a different slow policy-rate-regime signal, but shares macro/FOMC and exposure-overlay research lineage.

## Can public authoritative Fed data satisfy the frozen policy rule?

**Mostly, with a manual/automated source-reconstruction and validation step; not by consuming a single daily rate series as-is.** The Federal Reserve’s Open Market Operations page and archive publish dated target-rate changes and levels, including historical target levels; the FOMC calendar links meeting statements and implementation notes. FRED’s `DFEDTAR` / `DFEDTARL` / `DFEDTARU` series are official Board of Governors data distributed via the St. Louis Fed, but their daily effective-date observations do not by themselves preserve the original statement-publication timestamp required by the preregistration.

Primary-source references checked on 2026-11-07:

- [Federal Reserve, Open Market Operations](https://www.federalreserve.gov/monetarypolicy/openmarket.htm): annual tables of target changes and levels.
- [Federal Reserve, Open Market Operations Archive](https://www.federalreserve.gov/monetarypolicy/openmarket_archive.htm): historical policy target change/level table; the archive extends into the 1990s.
- [Federal Reserve, FOMC meeting calendars and information](https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm): links scheduled meetings to statements and implementation notes.
- [FRED, Federal Funds Target Range series](https://fred.stlouisfed.org/series/DFEDTARU): source is the Board of Governors; the series is a daily effective target-range boundary series, not an announcement-timestamp ledger.
- [NYSE, Holidays & Trading Hours](https://www.nyse.com/trade/hours-calendars): official calendar information currently published for forward years, useful for current regular-session rules but not by itself a complete historical session file.

The exact frozen rule needs a row for every scheduled policy decision, including no-change decisions, with the stated target/range, official source document, and publication timestamp. The Fed’s change/level archive is useful for rate reconstruction but appears to list changes rather than a complete event ledger of every scheduled no-change decision. FOMC calendar/statements provide the meeting records, but dates alone are insufficient for the preregistered strict timestamp-to-next-session mapping. Do not substitute an assumed universal 2 p.m. time or a daily FRED effective date for a verified statement timestamp. Where a statement’s timestamp cannot be verified, the candidate’s own fail-closed rule blocks that event.

The target-range transition can be handled by the preregistered midpoint rule, but historical pre-range policy targets and the range-era observations must be independently reconciled so no realized effective fed-funds series is accidentally spliced in. The available public sources make this tractable; completeness is not established until a row-by-row event audit and immutable source snapshots/hashes exist.

## SPY and calendar readiness

**The local SPY series is sufficient to prototype mechanics, but insufficient as-is for a confirmatory/authoritative result.**

- The existing SPY file spans 1993-01-29 to 2026-11-02, so it covers the main modern FOMC-announcement era and can support a descriptive SPY-only prototype if the event history is reconstructed. Because the first target comparison needs a full prior 365-day policy history, the usable start date must be derived from validated event coverage, not assumed to equal the first SPY row.
- The file’s recorded provenance is an unofficial Yahoo chart endpoint. A local hash identifies the snapshot but does not establish licensing, vendor correctness, corporate-action audit, survivorship concerns in the adjustment factors, or historical OHLC/calendar completeness.
- `adjclose` allows the preregistered adjusted-open formula to be computed, but no corporate-action audit was performed here. The formula and source need validation against splits/dividends and the intended total-return convention before performance access.
- The preregistration requires a verified US exchange calendar and first regular-session open strictly after statement publication. The local SPY date index can be checked for consistency, but because it shares the same unofficial feed it is not independent authoritative calendar proof. NYSE’s published holiday page is authoritative for rules/current calendars; a reproducible historical-session source or a carefully documented official calendar reconstruction is still needed for the full backtest period.
- Intraday timestamp-to-open mapping needs timezone/DST handling (`America/New_York`), weekends, holidays, and early closes. The policy says next regular-session open, so early-close days do not change the open mapping, but session existence must be exact.

## Overlap and multiplicity treatment

This is not a new independent strategy family. It is a **macro/FOMC exposure overlay**. Count it as dependent with:

1. the prior crypto-source FOMC time-window overlay cataloged in `FEASIBILITY.md` (different signal semantics, same event family), and
2. the already tested broad-market cash/exposure filters, including trend/breadth/cash overlays (shared portfolio action and benchmark comparison).

Do not treat a pass as independent confirmation or claim DSR/PSR/BH significance from this single preregistration. The exact cumulative trial count remains unresolved per the candidate and project ledger. Because the candidate is SPY-only, the KR PIT data gap is irrelevant to running this exact candidate, but it does not help satisfy the project-wide goal of finding strategies in both KR and US.

## GO dependencies

1. **Event table:** Build a complete scheduled-FOMC event table across the proposed scored period plus at least 365 days of prior target history. Include event date/classification, announced point target or range, exact official statement publication timestamp with timezone and evidence, source URL/document ID, retrieved-at/version, raw snapshot hash, and explicit missing/ambiguous status. Include no-change decisions. Reconcile every rate change against the official Fed archive; do not fill timestamp gaps with a convention.
2. **Source coverage audit:** Establish the first eligible scoring date from the first fully verified trailing-365-day comparison. Record policy target regime changes and all source gaps. Any unresolved event required by the rule means fail closed / no run.
3. **Benchmark authorization and provenance:** Decide whether the unofficial Yahoo SPY mirror is acceptable for an exploratory run. For stronger evidence, obtain a licensed/audited SPY total-return OHLC source or independently reconcile the local series’ adjusted-open factors, splits/dividends, missing sessions, and end-of-period conventions. Preserve the exact source/version and hash.
4. **Calendar:** Freeze and hash a historical US regular-session calendar, including relevant exceptional closures, and test timestamp mapping around before-open, after-open, holiday, weekend, DST, and date-only/unknown timestamp cases. Calendar-source derivation must be independent of return outcomes.
5. **Independent review and execution gate:** Review the frozen event table, rule-to-event mapping, benchmark inputs, and future runner/tests; hash the artifacts; obtain explicit root GO before any SPY price-value access. No runner presently exists.
6. **Multiplicity:** Reconcile the whole experiment ledger and count prior related FOMC/cash-overlay trials before any significance language. Keep prior trials in the dependence family even when their time horizon differs.

## Readiness conclusion

- **Fed event data:** obtainable from authoritative, free Fed pages in principle; the strict timestamp-complete event ledger is not already present and must be constructed/audited.
- **Local SPY data:** date/schema coverage exists, but source provenance and corporate-action/calendar validation do not meet a strong confirmatory gate as currently documented.
- **Implementation:** not ready; no runner/tests/event table exist.
- **Research novelty:** distinct from price-derived signals but overlapping with prior macro event and cash-overlay families.
- **Performance path:** not executed; no strategy verdict.

## Sources

- Federal Reserve Board, [Open Market Operations](https://www.federalreserve.gov/monetarypolicy/openmarket.htm).
- Federal Reserve Board, [Open Market Operations Archive](https://www.federalreserve.gov/monetarypolicy/openmarket_archive.htm).
- Federal Reserve Board, [FOMC meeting calendars and information](https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm).
- Federal Reserve Board series via FRED, [Federal Funds Target Range - Upper Limit (DFEDTARU)](https://fred.stlouisfed.org/series/DFEDTARU).
- NYSE, [Holidays & Trading Hours](https://www.nyse.com/trade/hours-calendars).
