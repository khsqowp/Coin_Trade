# Round 2 — one-time corrected-rule review

Date: 2026-11-16 (Asia/Seoul)
Scope: compare the 13 corrected definitions with their original Round 1 registrations and the user-fixed scope. This is a rule-integrity review only. No performance trial, market-data read, or OOS access occurred.

## Decision

**0 pass, 4 reject, 9 conditional. No candidate is approved for a performance test.** Four corrected definitions either omit a registered condition or retain material ambiguity. The single permitted correction is exhausted; do not revise these four again or replace them under new IDs. The remaining nine are conditional only because data rights, point-in-time fields/universes, execution costs, benchmark, and/or historical coverage remain unverified.

| Candidate | Verdict | Finding |
|---|---|---|
| KR-01 Earnings surprise drift | Reject | The correction omits the original registered exclusion for a >5% gap within five sessions after disclosure. Its reference price/measurement is itself not defined in the registration. Omitting the condition changes the frozen rule; a second correction is not allowed. |
| KR-02 KOSPI 200 reconstitution | Conditional | Event/version and withdrawal handling are now specified. PIT constituent notices, inactive names, and price history remain unverified. |
| KR-04 Foreign-flow/price confirmation | Reject | Entry uses a latest-five-session flow aggregate, but the exit “flow turns negative” is not defined as daily flow or the same five-session aggregate. The exit state is therefore not uniquely codeable after the one correction. |
| KR-05 Closing-auction program imbalance | Conditional | Population, ranking, publication, and next-open fill/miss rules are explicit. Historical auction/NBBO/fill data and executable costs remain absent; do not substitute daily bars. |
| KR-06 IPO lock-up supply absorption | Conditional | Actual release date, float denominator, reference close, and two-session value sum are explicit. Actual release/quantity, PIT float, and inactive IPO history remain unverified. |
| KR-07 Cash-dividend surprise | Reject | The original top-decile condition is estimated dividend-yield surprise. The correction replaces that ranking variable with DPS surprise; this changes the registered signal rather than clarifying it. No second correction is allowed. |
| KR-10 Shareholder meeting/governance event | Conditional | Structured original agenda fields and filing-version timestamps are specified; vote outcomes are excluded from entry. Historical structured agenda/vintages and inactive-name outcomes remain unverified. |
| US-04 Schedule 13D activist filing | Reject | The stop “2 ATR from the post-filing low” still has no exact level/formula or ATR sampling time. The general ATR availability rule does not resolve whether the stop is low minus 2 ATR, a subsequent trailing level, or another rule. No second correction is allowed. |
| US-05 Actual buyback execution progress | Conditional | Filing-vintage cumulative purchased shares and plan denominator are specified; ambiguous or incompatible denominator units are excluded. As-filed quantities and correction history remain unavailable. |
| US-06 ETF net creations | Conditional | The equity ETF universe and flow formula are explicit. PIT shares/NAV/AUM, identifier mapping, inactive funds, and distribution-adjusted returns remain unverified. |
| US-07 Regular cash-dividend change | Conditional | Regular-dividend classification, comparison basis, and event timing are specified. Full as-filed history, distributions, delisted outcomes, and total-return inputs remain unverified. |
| US-08 IPO lock-up short | Conditional | Actual tradability, float, volume, next-open entry, borrow, adverse stop, and forced-cover evidence are stated. Historical actual-release and security-level borrow/recall records remain unavailable. |
| US-09 Index change | Conditional | Addition/deletion direction, PIT notice versions, borrow gate, skip rule, and duplicate clustering are specified. Complete historical notices, borrow, inactive names, and event execution data remain unverified. |

## Count and stop conditions

- Round 1 final disposition: 0 pass, 17 reject, 13 conditional across 30 proposals; performance trials = 0.
- Round 2 corrected-rule review: 0 pass, 4 newly rejected, 9 remain conditional; Round 2 performance trials = 0 and valid OOS events = 0.
- Rejected Round 2 rules cannot receive another correction or be relabeled as new candidates. The nine conditional rules are not eligible until their individual data and cost gates are documented and independently reviewed.
- Crypto remains at 0 eligible candidates from Round 1. Existing R021 funding re-entry was rejected at 34.1–48.3% target-first across its tested timeframe/horizon cells; R025 tested all 15 non-empty subsets of four frozen atoms, with no cell reaching 80%. These are exposed historical-development results, not a fresh OOS result. Do not repackage the funding/basis family as novel.
- Crypto primary success criterion is target touched before invalidation/stop and deadline, with >=80% precision and >=200 non-overlapping OOS events per claim. Deadline-close directional accuracy is secondary and separately reported. The accessible source-data gate is still closed; no current performance claim is made.

## Review provenance and limits

The corrected rules were compared line-by-line against `round1_candidate_register_20261116.md`, `round1_redteam_audit_20261116.md`, and `round2_conditional_rule_revisions_20261116.md`. A delegated independent review could not read the local checkout due to its isolated filesystem and returned no candidate-level verdicts; the decisions above are the chief's own documented comparison, not an independent-agent result. The existing R021 and R025 decision records were consulted for duplicate-family control. No market-data rows, sealed partitions, or performance calculations were opened or generated in this review.
