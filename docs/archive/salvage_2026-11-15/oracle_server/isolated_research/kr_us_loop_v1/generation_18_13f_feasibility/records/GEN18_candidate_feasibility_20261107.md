# Gen18 candidate-family feasibility review

Date: 2026-11-07

## Decision

Do not preregister another close-only indicator variant against the current cache. Three independent reviews found no clearly distinct candidate with adequate evidence to justify another immediate test. More transformations of OHLC close/volume into named indicators would expand the multiple-testing burden without solving the cohort, OOS, rights, or PIT limitations.

## Candidate-family review

- Reviewed against the local cumulative log: momentum/trend, directional/trend state, reversal/short-term rebound, calendar/seasonality, panic reversal, low volatility/downside semivariance, low-skew, event-gap acceptance, and earlier factor/crypto strategy ideas. Avoid relabeling these families as new discoveries.
- A 126-session low-beta ranking could be calculated from the existing cohort panel, but is a low-risk/low-volatility relative, not a genuinely independent family. A cohort of 7 US and 21 KR survivors makes its estimates unstable and non-PIT. It is not recommended as the next counted candidate.
- More distinct feasibility leads are information-event or ownership-flow signals: US SEC Form 13F ownership accumulation, as-filed earnings announcement drift (PEAD/SUE), and Korean DART ownership/earnings disclosures. The local log already records Form 4 and SUE leads. These should remain feasibility leads, not performance candidates, until source access, permitted derived use, filing timestamps/amendments, historical security mapping, and PIT price/universe coverage are evidenced.

## Independent reviews

- Strategy reviewer A: rejected re-running the opening-gap family because a frozen Gen14 gap-acceptance preregistration already exists; proposed low beta only as a correlated low-risk variant.
- Strategy reviewer B: found no materially distinct ready-to-test close-only idea; suggested 13F institutional ownership flow for feasibility-only review.
- Red-team reviewer C: proposed PEAD as a distinct information-event family, but required as-filed/accepted timestamps, earnings surprise definition, amendment handling, same-day event rules, PIT securities and prices, and independent OOS before preregistration.
- Data reviewer: blocked at source verification. `agent-reach doctor --json` could not run because the executable is absent. The skill's documented Exa route (`mcporter call exa.web_search_exa`) failed MCP version negotiation (`fetch failed`). No documented retry path was available, so no alternative search tool was used. Existing local notes do not establish current source rights or completeness for 13F/PEAD/DART.

## Disposition and next admissible work

- Status: `FEASIBILITY_BLOCKED`; no Gen18 hypothesis frozen, no market data accessed, and no performance metrics computed.
- Restore the approved Agent Reach/Exa research route, then verify official primary documentation and data-specific terms for 13F and PEAD before deciding which one can be preregistered. Do not create an account, request a key, accept terms, or use paid data without separate authorization.
- In parallel, prioritize a genuinely admissible PIT price/universe route or prospective paper-data collection. Do not call the Gen17 US numerical screen a valid strategy; its post-unseal implementation reconciliation does not cure its preregistration sequencing deviation.
- Count of valid strategies: **0/2**.

## Official-source follow-up — SEC 13F feasibility

After the documented Agent Reach connection failure, the root used the available official web search/read path as a fallback; this fallback was announced, and only primary SEC/DART pages were used. No data ZIP was downloaded and no API was called.

- SEC's 13F data-sets page states that the flattened structured-XML records are presented unchanged from the as-filed submissions and currently lists coverage from July 2013 through August 2026. It updates quarterly, warns that compilation may contain errors and omits some filing metadata, and says some filings after 5:30 p.m. Eastern on the final business day of a quarter roll into the next dataset. Source: https://www.sec.gov/data-research/sec-markets-data/form-13f-data-sets
- SEC's `data.sec.gov` submissions/XBRL API documentation states the API requires no authentication or API key, and describes real-time filing updates and nightly bulk archives. This establishes public access to filing history, not completeness of an executable 13F signal or rights to any separate price dataset. Source: https://www.sec.gov/search-filings/edgar-application-programming-interfaces
- SEC's current Form 13F FAQ states quarterly filings are due within 45 days of quarter-end and distinguishes original `13F-HR` and amendment `13F-HR/A` filings. Signals therefore must use actual EDGAR acceptance time, never quarter-end as if holdings were then observable. Sources: https://www.sec.gov/rules-regulations/staff-guidance/frequently-asked-questions-about-form-13f and https://www.sec.gov/about/developer-resources
- OpenDART describes access to original disclosure XML and structured financial data; the portal exposes an API-key application. No key was requested or created. Sources: https://opendart.fss.or.kr/intro/main.do and https://opendart.fss.or.kr/

### Revised Gen18 status

**Source lead passes; strategy data gate remains blocked.** A fixed US-only institutional ownership breadth hypothesis can be specified from as-filed 13F records, but there is no validated historical CUSIP-to-security crosswalk, split/corporate-action adjustment, complete PIT manager/security coverage, or admissible PIT price panel. The SEC dataset disclaimer also requires raw-filing validation for amendment, joint-manager, missing-report and metadata cases. Thus no frozen performance preregistration or market-return test is authorized yet.

An independent rule sketch proposed: compare consecutive original filings available by a fixed report-date-plus-60-day cutoff; compute same-security manager share-count changes only after effective split adjustment; rank a fixed US universe by positive/negative institutional breadth; enter only after the public filing cutoff. This remains a design note, not a registered rule, because the CUSIP map, shared-discretion deduplication, eligibility, missing/late filing, benchmark, price rights and execution fields are unresolved. Three-agent red-team review classifies current 13F return testing `DATA_BLOCKED`.
